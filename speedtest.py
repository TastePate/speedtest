import argparse
import http.client
import math
import sys
import time
from urllib.error import URLError
from urllib.parse import urlsplit
from urllib.request import Request, urlopen

REQUEST_COUNT = 10
CHUNK_SIZE = 64 * 1024


def http_url(value):
    try:
        parts = urlsplit(value)
        if parts.scheme not in ("http", "https") or not parts.hostname:
            raise ValueError
        parts.port
    except ValueError:
        raise argparse.ArgumentTypeError("Укажите корректный HTTP или HTTPS адрес.")
    return value


def positive_timeout(value):
    try:
        number = float(value)
        if not math.isfinite(number) or number <= 0:
            raise ValueError
    except ValueError:
        raise argparse.ArgumentTypeError("Таймаут должен быть положительным числом.")
    return number


def download(url, timeout):
    request = Request(url, headers={
        "User-Agent": "internet-speedtest/1.0",
        "Accept-Encoding": "identity",
        "Cache-Control": "no-cache",
    })
    size = 0
    started = time.perf_counter()
    with urlopen(request, timeout=timeout) as response:
        expected = response.headers.get("Content-Length")
        while chunk := response.read(CHUNK_SIZE):
            size += len(chunk)
        if expected is not None and size != int(expected):
            raise OSError("Сервер передал неполный ответ.")
    return size, time.perf_counter() - started


def main(argv=None):
    parser = argparse.ArgumentParser(description="Замер скорости: 10 последовательных скачиваний.")
    parser.add_argument("url", type=http_url, help="Прямая ссылка на большой файл или картинку")
    parser.add_argument("--timeout", type=positive_timeout, default=30,
                        help="Таймаут сетевой операции в секундах (по умолчанию 30)")
    args = parser.parse_args(argv)
    total_size = 0
    total_time = 0.0
    for index in range(1, REQUEST_COUNT + 1):
        try:
            size, elapsed = download(args.url, args.timeout)
        except (URLError, OSError, ValueError, http.client.HTTPException) as error:
            print(f"Запрос {index}/{REQUEST_COUNT}: ошибка: {error}", file=sys.stderr)
            return 1
        total_size += size
        total_time += elapsed
        print(f"Запрос {index}/{REQUEST_COUNT}: {size} байт за {elapsed:.3f} с")

    speed = total_size / total_time / 1_000_000
    print(f"\nСреднее время запроса: {total_time / REQUEST_COUNT:.3f} с")
    print(f"Скачано всего: {total_size} байт ({total_size / 1_000_000:.3f} МБ)")
    print(f"Скорость: {speed:.3f} МБ/с ({speed * 8:.3f} Мбит/с)")
    return 0


if __name__ == "__main__":
    try:
        sys.exit(main())
    except KeyboardInterrupt:
        print("\nЗамер прерван.", file=sys.stderr)
        sys.exit(130)
