import unittest

from admin_disp.core.sa_compat import SACompatConnection


class _FakeResult:
    def __init__(self, rows=None, keys=None, rowcount=0, returns_rows=True):
        self._rows = rows or []
        self._keys = keys or []
        self.rowcount = rowcount
        self.returns_rows = returns_rows

    def fetchall(self):
        return self._rows

    def keys(self):
        return self._keys


class _FakeConn:
    def __init__(self):
        self.commits = 0
        self.rollbacks = 0
        self.closed = False
        self.calls = []

    def exec_driver_sql(self, sql, params):
        self.calls.append((sql, params))
        if "SELECT" in sql.upper():
            return _FakeResult(rows=[("a", 1), ("b", 2)], keys=["name", "val"], rowcount=2, returns_rows=True)
        return _FakeResult(rows=[], keys=[], rowcount=1, returns_rows=False)

    def commit(self):
        self.commits += 1

    def rollback(self):
        self.rollbacks += 1

    def close(self):
        self.closed = True


class _FakeEngine:
    def __init__(self):
        self.conn = _FakeConn()

    def connect(self):
        return self.conn


class SACompatConnectionTests(unittest.TestCase):
    def test_cursor_execute_fetch_and_description(self):
        engine = _FakeEngine()
        db = SACompatConnection(engine)
        cur = db.cursor()

        cur.execute("SELECT name, val FROM t WHERE id = ?", (1,))
        one = cur.fetchone()
        rest = cur.fetchall()

        self.assertEqual(one, ("a", 1))
        self.assertEqual(rest, [("b", 2)])
        self.assertIsNotNone(cur.description)
        self.assertEqual(cur.description[0][0], "name")

    def test_autocommit_true_commits_after_execute(self):
        engine = _FakeEngine()
        db = SACompatConnection(engine)
        db.autocommit = True
        cur = db.cursor()

        cur.execute("UPDATE t SET x = ? WHERE id = ?", (3, 1))

        self.assertEqual(engine.conn.commits, 1)

    def test_commit_and_rollback_delegate(self):
        engine = _FakeEngine()
        db = SACompatConnection(engine)

        db.commit()
        db.rollback()

        self.assertEqual(engine.conn.commits, 1)
        self.assertEqual(engine.conn.rollbacks, 1)


if __name__ == "__main__":
    unittest.main()
