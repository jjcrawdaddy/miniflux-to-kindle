import logging
import os
import time

import schedule

logger = logging.getLogger(__name__)


def main() -> None:
    logging.basicConfig(level=logging.INFO, format='%(asctime)s %(levelname)s %(message)s')


if __name__ == '__main__':
    main()
