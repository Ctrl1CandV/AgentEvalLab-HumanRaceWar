"""Static policy and public-rule regressions; no bot execution here."""
import ast
import errno
import struct
import unittest
from unittest.mock import patch

from arena.core.seccomp import runtime_filter
from arena.core.sandbox import ROOT


def evaluate(policy, number, flags=0, arch=0xC000003E):
    instructions = list(struct.iter_unpack("=HBBI", policy))
    memory = {0: number, 4: arch, 16: flags}
    pc = accumulator = 0
    for _ in range(len(instructions)):
        code, jt, jf, value = instructions[pc]
        pc += 1
        if code == 0x20: accumulator = memory[value]
        elif code == 0x15: pc += jt if accumulator == value else jf
        elif code == 0x35: pc += jt if accumulator >= value else jf
        elif code == 0x45: pc += jt if accumulator & value else jf
        elif code == 0x06: return value
        else: raise AssertionError(f"unsupported instruction {code}")
    raise AssertionError("policy did not return")


class ReviewPolicyTests(unittest.TestCase):
    def test_seccomp_arch_clone_and_affinity_branches(self):
        with patch("arena.core.seccomp.platform.machine", return_value="x86_64"):
            policy = runtime_filter()
        for number in (57, 58, 203, 101, 310, 311, 272, 308, 319, 29, 64, 68, 240):
            self.assertEqual(evaluate(policy, number), 0x50000 | errno.EPERM)
        self.assertEqual(evaluate(policy, 435), 0x50000 | errno.ENOSYS)
        self.assertEqual(evaluate(policy, 56, 17), 0x50000 | errno.EPERM)
        self.assertEqual(evaluate(policy, 56, 0x10000 | 0x100 | 0x800), 0x7FFF0000)
        self.assertEqual(evaluate(policy, 1), 0x7FFF0000)
        self.assertEqual(evaluate(policy, 1, arch=0x40000003), 0x80000000)
        self.assertEqual(evaluate(policy, 0x40000000 | 57), 0x80000000)
        with patch("arena.core.seccomp.platform.machine", return_value="unsupported"), self.assertRaises(RuntimeError):
            runtime_filter()

    def test_model_rules_contain_no_scoring_formula_or_process_metrics(self):
        text = (ROOT / "rules/rules.md").read_text()
        for token in ("过程分", "0.75", "0.25", "0.4", "0.3", "等权平均"):
            self.assertNotIn(token, text)
        for token in ("main.py", "*.cpp", "16 MiB", "64 MiB", "2 GiB", "只读", "下一回合"):
            self.assertIn(token, text)

    def test_all_invalid_reason_codes_are_documented(self):
        codes = set()
        for name in ("orders.py", "engine.py"):
            tree = ast.parse((ROOT / "arena/games/outpost" / name).read_text())
            for node in ast.walk(tree):
                value = None
                if isinstance(node, ast.Return):
                    result = node.value.orelse if isinstance(node.value, ast.IfExp) else node.value
                    if isinstance(result, ast.Constant): value = result.value
                elif isinstance(node, ast.Call) and node.args:
                    called = node.func.id if isinstance(node.func, ast.Name) else getattr(node.func, "attr", "")
                    if called in ("warn", "_invalid") and isinstance(node.args[-1], ast.Constant):
                        value = node.args[-1].value
                elif isinstance(node, ast.Constant) and isinstance(node.value, str) and node.value.startswith("MOVE_"):
                    value = node.value
                if isinstance(value, str) and value.isupper(): codes.add(value)
        text = (ROOT / "rules/rules.md").read_text()
        self.assertEqual(len(codes), 31)
        for code in codes: self.assertIn(f"`{code}`", text)


if __name__ == "__main__":
    unittest.main()
