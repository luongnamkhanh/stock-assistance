"""Chay toan bo test module (8 module, danh sach da day du)."""
MODULES = ["tests.test_config", "tests.test_domain", "tests.test_repo", "tests.test_feeds",
           "tests.test_presenters", "tests.test_infra_misc",
           "tests.test_usecases", "tests.test_bot"]

def main():
    import importlib
    for name in MODULES:
        importlib.import_module(name).run()
    print("ALL TESTS OK")

if __name__ == "__main__":
    main()
