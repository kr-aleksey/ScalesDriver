import logging
import time

from scales_driver.drivers import CASType6, Generic
from scales_driver.exceptions import SerialError, ScalesException

# Serial params
PORT = 'com6'
BAUDRATE = 9600
BYTESIZE = 8
PARITY = 'N'
STOPBITS = 1
TIMEOUT = 1

# Scales params
DRIVER = CASType6
RETRY_TIME = 0.3
RECOVERY_TIME = 5
DECIMAL_PLACES = 1

# Logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s %(levelname)s: %(message)s'
)

# Statuses
STATUS: dict[int, str] = {
    Generic.STATUS_OVERLOAD: 'Overload',
    Generic.STATUS_STABLE: 'Stable',
    Generic.STATUS_UNSTABLE: 'Unstable',
}


def main():
    scales = DRIVER(port=PORT,
                    baudrate=BAUDRATE,
                    bytesize=BYTESIZE,
                    parity=PARITY,
                    stopbits=STOPBITS,
                    timeout=TIMEOUT)
    logging.info('Starting...')
    initialized = False
    while not initialized:
        try:
            initialized = scales.scales_init()
        except SerialError:
            time.sleep(RECOVERY_TIME)
    logging.info('Process is started.')

    print('\033[36m\033[40m\033[1m', end='')
    while True:
        try:
            scales.update()
            data = scales.get_weight(unit=Generic.GR, decimal_places=1)
            status = STATUS.get(scales.get_status())
            print(' ' * 20, '\r', end='')
            print(data, Generic.GR, status, end='', flush=True)
            time.sleep(RETRY_TIME)
        except ScalesException as error:
            pass
        except SerialError as error:
            pass
            time.sleep(RECOVERY_TIME)
            scales.scales_reinit()


if __name__ == '__main__':
    main()
