"""Synthetic formatter regressions; never import/start the Telegram bot.

Only the literal bit-count table and vas100 function are selected from its AST.
No Telegram imports, module-level log open, handlers, or polling are executed.
"""
import ast
from decimal import Decimal
import hashlib
import html
import os
from pathlib import Path
import re
from types import SimpleNamespace
import unittest


SOURCE = Path(os.environ.get('VAS100_TEST_SOURCE',
                            Path(__file__).resolve().parents[1] / 'bot/bot.py'))


def load_function(hash_api, random_api=None):
    tree = ast.parse(SOURCE.read_text())
    table = next(node for node in tree.body
                 if isinstance(node, ast.Assign)
                 and any(isinstance(target, ast.Name) and target.id == 'hex2ones'
                         for target in node.targets))
    function = next(node for node in tree.body
                    if isinstance(node, ast.FunctionDef) and node.name == 'vas100')
    namespace = {'hex2ones': ast.literal_eval(table.value), 'hashlib': hash_api,
                 'html': html, 're': re, 'random': random_api}
    exec(compile(ast.Module(body=[function], type_ignores=[]), str(SOURCE), 'exec'),
         namespace)
    return namespace['vas100']


def run_digest(one_bits, seed='synthetic seed', suffix='0' * 39):
    # Construct all 101 possible one-bit counts directly; no seed search/miner.
    bits = '1' * one_bits + '0' * (100 - one_bits)
    prefix = f'{int(bits, 2):025x}'
    captured = []
    digest = SimpleNamespace(update=captured.append,
                             hexdigest=lambda: prefix + suffix)
    result = load_function(SimpleNamespace(sha256=lambda: digest))(seed, False)
    return result, prefix, captured


def multiplier(output):
    return re.search(r'<b>x([^<]+)</b>', output).group(1)


class MultiplierDisplayTest(unittest.TestCase):
    def test_every_possible_bit_count_keeps_positive_multiplier_and_mapping(self):
        for ones in range(101):
            with self.subTest(one_bits=ones):
                (exponent, seed, short_hash, output), prefix, captured = run_digest(ones)
                self.assertEqual(exponent, 3 * ones - 200)
                self.assertEqual(seed, 'synthetic seed')
                self.assertEqual(captured, [seed.encode()])
                self.assertEqual(short_hash, prefix[:13])
                self.assertIn(f'100 бит SHA-256</b> {prefix}', output)
                self.assertIn(f'{ones} x "1", {100 - ones} x "0"', output)
                self.assertGreater(Decimal(multiplier(output)), 0)

    def test_minimum_multiplier_has_a_nonzero_approximation(self):
        result, _, _ = run_digest(0)
        self.assertEqual(result[0], -200)
        self.assertEqual(multiplier(result[3]), '6.22e-61')

    def test_fallback_precision_for_all_previously_zero_values(self):
        for ones in range(11):
            with self.subTest(one_bits=ones):
                result, _, _ = run_digest(ones)
                represented = Decimal(multiplier(result[3]))
                exact = Decimal(2) ** result[0]
                self.assertLess(abs(represented - exact) / exact, Decimal('0.005'))

    def test_zero_display_boundary_preserves_adjacent_nonzero_format(self):
        zero_before, _, _ = run_digest(10)
        nonzero_before, _, _ = run_digest(11)
        self.assertEqual(zero_before[0], -170)
        self.assertEqual(multiplier(zero_before[3]), '6.68e-52')
        self.assertEqual(nonzero_before[0], -167)
        self.assertEqual(multiplier(nonzero_before[3]), '0.' + '0' * 49 + '1')

    def test_normal_display_representations_are_unchanged(self):
        expected = {64: '0.0039', 65: '0.031', 66: '0.25', 67: '2',
                    68: '16', 69: '128', 70: '1024',
                    100: '1267650600228229401496703205376'}
        for ones, text in expected.items():
            with self.subTest(one_bits=ones):
                result, _, _ = run_digest(ones)
                self.assertEqual(multiplier(result[3]), text)

    def test_bits_after_first_hundred_do_not_change_result(self):
        first, _, _ = run_digest(40, suffix='0' * 39)
        second, _, _ = run_digest(40, suffix='f' * 39)
        self.assertEqual(first, second)

    def test_seed_html_is_escaped_without_changing_hash_input(self):
        seed = '<>&"\''
        result, _, captured = run_digest(0, seed=seed)
        self.assertEqual(result[1], seed)
        self.assertEqual(captured, [seed.encode()])
        self.assertIn('<code>&lt;&gt;&amp;&quot;&#x27;</code>', result[3])
        self.assertNotIn('<code>' + seed + '</code>', result[3])

    def test_fixed_seed_uses_actual_sha256_and_utf8(self):
        for seed in ['fixed synthetic seed', 'синтетический сид 🚂']:
            with self.subTest(seed=seed):
                result = load_function(hashlib)(seed, False)
                prefix = hashlib.sha256(seed.encode()).hexdigest()[:25]
                expected_exponent = 3 * int(prefix, 16).bit_count() - 200
                self.assertEqual(result[:3], (expected_exponent, seed, prefix[:13]))
                self.assertIn(prefix, result[3])

    def test_random_seed_branch_preserves_bounds_and_selected_seed(self):
        calls = []

        def randint(lower, upper):
            calls.append((lower, upper))
            return -123

        result = load_function(hashlib, SimpleNamespace(randint=randint))('', True)
        self.assertEqual(calls, [(-2**63, 2**63-1)])
        ordinary = load_function(hashlib)('-123', False)
        self.assertEqual(result[:3], ordinary[:3])
        self.assertIn('рандомный (пустой) сид:', result[3])
        self.assertEqual(multiplier(result[3]), multiplier(ordinary[3]))


if __name__ == '__main__':
    unittest.main()
