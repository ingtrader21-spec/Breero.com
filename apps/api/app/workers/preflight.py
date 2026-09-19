from app.workers.celery_app import assert_expected_beat_tasks


def main() -> None:
    assert_expected_beat_tasks()


if __name__ == "__main__":
    main()
