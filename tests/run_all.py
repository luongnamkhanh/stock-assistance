"""Chay toan bo test module. Moi task them 1 dong import + goi run()."""
MODULES = ["tests.test_config"]  # cac task sau append: ("tests.test_config", ...)

def main():
    import importlib
    for name in MODULES:
        importlib.import_module(name).run()
    print("ALL TESTS OK")

if __name__ == "__main__":
    main()
