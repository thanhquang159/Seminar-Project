def pytest_addoption(parser):
    parser.addoption(
        "--run-publication-db",
        action="store_true",
        default=False,
        help="Chạy test publish trên PostgreSQL cấu hình hiện tại, mọi ghi dữ liệu đều rollback.",
    )
