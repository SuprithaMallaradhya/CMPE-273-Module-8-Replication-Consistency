"""Run the assignment's reproducible replication and stale-read demonstration."""

from inventory import InventorySystem


def show(system):
    primary = system.read("primary")
    secondary = system.read("secondary")
    print(f"CLIENT READ primary:   stock={primary.stock}, version={primary.version}")
    print(f"CLIENT READ secondary: stock={secondary.stock}, version={secondary.version}")
    return primary, secondary


def check(condition, message):
    if not condition:
        raise AssertionError(message)
    print(f"PASS: {message}")


def main():
    print("MODULE 8: REPLICATION & CONSISTENCY")
    print("One primary | One secondary | Client-selectable reads")
    with InventorySystem(stock=10) as system:
        print("\n=== 1. SUCCESSFUL REPLICATION ===")
        print("Initial state:")
        show(system)
        written = system.update(11)
        print(f"WRITE primary: stock={written.stock}, version={written.version}")
        check(system.read("primary") == written, "primary receives the new value")
        system.wait_for_version(written.version)
        primary, secondary = show(system)
        check(primary == secondary == written, "both replicas contain stock=11 after replication")

        print("\n=== 2. STALE READ WHILE REPLICATION IS PAUSED ===")
        baseline = system.update(10)
        system.wait_for_version(baseline.version)
        print("Reset both replicas to the required stock=10 baseline:")
        show(system)
        system.pause_replication()
        print("REPLICATION PAUSED: secondary delivery is delayed; reads remain available")
        written = system.update(9)
        print(f"WRITE primary: stock={written.stock}, version={written.version} (queued for secondary)")
        primary, secondary = show(system)
        check(primary.stock == 9 and secondary.stock == 10,
              "stale read observed: primary=9, secondary=10")
        check(secondary.version < primary.version, "secondary is behind the primary version")

        print("\n=== 3. RECOVERY AND CONVERGENCE ===")
        system.resume_replication()
        print("REPLICATION RESUMED: background worker delivers the queued update")
        system.wait_for_version(written.version)
        primary, secondary = show(system)
        check(primary == secondary == written, "replicas converge to stock=9 at the same version")
    print("\nALL DEMONSTRATIONS PASSED")


if __name__ == "__main__":
    main()
