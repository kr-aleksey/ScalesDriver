import logging
from decimal import Decimal, ROUND_05UP
from typing import Optional, Union

from serial import Serial, SerialException

from exceptions import ScalesException, SerialError


class Generic:
    GR: str = 'gr'
    KG: str = 'kg'
    LB: str = 'lb'
    STATUS_OVERLOAD: int = 0
    STATUS_STABLE: int = 1
    STATUS_UNSTABLE: int = 2

    FACTOR: dict[str, Decimal] = {
        GR: Decimal(1),
        KG: Decimal(1000),
        LB: Decimal(453.595),
    }

    def __init__(self, port, baudrate, bytesize, parity, stopbits, timeout) -> None:
        self.port_params = {
            'port': port,
            'baudrate': baudrate,
            'bytesize': bytesize,
            'parity': parity,
            'stopbits': stopbits,
            'timeout': timeout
        }
        self.port: Serial = Serial()
        self.weight: Decimal = Decimal(0)
        self.status: int = self.STATUS_OVERLOAD
        self.unit: str = self.GR

    def scales_init(self) -> bool:
        """Serial initialization"""
        self.port.port = self.port_params['port']
        self.port.baudrate = self.port_params['baudrate']
        self.port.bytesize = self.port_params['bytesize']
        self.port.parity = self.port_params['parity']
        self.port.stopbits = self.port_params['stopbits']
        self.port.timeout = self.port_params['timeout']
        try:
            logging.debug(f'Opening a serial port {self.port.port}')
            self.port.open()
        except SerialException as error:
            raise SerialError(error)
        return self.port.is_open

    def scales_reinit(self):
        try:
            if self.port.is_open:
                self.port.close()
            self.port.open()
        except SerialException as error:
            logging.error(f'Device initialization error. {error}')

    def update(self):
        """Update scales data."""
        pass

    def get_status(self):
        """Return scales status."""
        return self.status

    def get_weight(self, unit: str, decimal_places: int) -> Decimal:
        """
        Weight conversion and rounding
        :param unit: weight unit
        :param decimal_places: digits after the decimal point
        :return: weight
        """
        factor: Optional[Decimal] = self.FACTOR.get(unit)
        if factor is None:
            raise ValueError(f'Unknown unit={unit}')
        scales_factor = self.FACTOR[self.unit]
        exp = Decimal(f'0.{"0" * decimal_places}')
        return (self.weight * scales_factor / factor).quantize(exp, ROUND_05UP)


class CASType6(Generic):
    """Driver CAS-M DC1 (CAS Type#6)."""
    ENQ: bytes = b'\x05'
    ACK: bytes = b'\x06'
    DC1: bytes = b'\x11'
    WRAP: bytes = b'\x01\x02\x03\x04'
    PREFIX_ADDR: slice = slice(0, 2)
    STA_ADDR: int = 2
    SIGN_ADDR: int = 3
    UNIT_ADDR: slice = slice(10, 12)
    DATA_ADDR: slice = slice(2, 12)
    WEIGHT_ADDR: slice = slice(3, 10)
    BCC_ADDR: int = 12
    SUBFIX_ADDR: slice = slice(13, 15)
    DATA_LEN: int = 15
    STATUS: dict[int, int] = {
        0x53: Generic.STATUS_STABLE,
        0x55: Generic.STATUS_UNSTABLE,
        0x46: Generic.STATUS_OVERLOAD,
    }
    UNIT: dict[bytes, str] = {
        b'\x20\x67': Generic.GR,
        b'\x6B\x67': Generic.KG,
        b'\x6C\x62': Generic.LB,
    }

    def __init__(self, port, baudrate, bytesize, parity, stopbits, timeout):
        super().__init__(port=port,
                         baudrate=baudrate,
                         bytesize=bytesize,
                         parity=parity,
                         stopbits=stopbits,
                         timeout=timeout)

    def read_data(self) -> bytes:
        """Read data from scales."""
        try:
            self.port.write(self.ENQ)
            ack: bytes = self.port.read()
            if ack != self.ACK:
                raise ScalesException(f'ACK="{ack!r}", expected "{self.ACK!r}"')
            self.port.write(self.DC1)
            return self.port.read(self.DATA_LEN)
        except SerialException as error:
            raise SerialError(error)

    def check_response(self, response: bytes) -> None:
        """Checking the correctness of the scales' response."""
        # response len
        response_len: int = len(response)
        if response_len != self.DATA_LEN:
            raise ScalesException(f'Response len={response_len}, expected {self.DATA_LEN}')
        # response wrap
        wrap: bytes = response[self.PREFIX_ADDR] + response[self.SUBFIX_ADDR]
        if wrap != self.WRAP:
            raise ScalesException(f'Response wrap={wrap!r}, expected {self.WRAP!r}')
        # response BCC
        data_bcc: int = self.bcc(response[self.DATA_ADDR])
        bcc: int = response[self.BCC_ADDR]
        if data_bcc != bcc:
            raise ScalesException(f'Computed BCC={data_bcc}, expected {bcc}')

    def parse_value(self, response: bytes) -> Decimal:
        """Parsing the weight value."""
        value: str = response[self.WEIGHT_ADDR].decode()
        return Decimal(value)

    def parse_unit(self, response: bytes) -> str:
        """Parsing the weight unit."""
        un: bytes = response[self.UNIT_ADDR]
        unit: Optional[str] = self.UNIT.get(un)
        if unit is None:
            units = ', '.join(map(str, self.UNIT))
            raise ScalesException(f'UN={un!r} not in [{units}]')
        return unit

    def parse_status(self, response: bytes) -> int:
        """Parsing the scales status."""
        sta: int = response[self.STA_ADDR]
        status: Optional[int] = self.STATUS.get(sta)
        if status is None:
            statuses = ', '.join(map(str, self.STATUS))
            raise ScalesException(f'STA={sta} not in [{statuses}]')
        return status

    def update(self) -> None:
        """Update data from scales."""
        try:
            logging.debug('Reading data from the scales')
            response: bytes = self.read_data()
            logging.debug('Checking the correctness of the scales response')
            self.check_response(response)
            logging.debug('Parsing the scales status')
            self.status: int = self.parse_status(response)
            logging.debug('Parsing the weight value')
            self.weight: Decimal = self.parse_value(response)
            logging.debug('Parsing the weight unit')
            self.unit: str = self.parse_unit(response)
        except Exception as Error:
            raise Error

    @staticmethod
    def bcc(data: Union[list[int], bytes]) -> int:
        """Returns BCC for sequence items."""
        bcc: int = 0
        for item in data:
            bcc ^= item
        return bcc
