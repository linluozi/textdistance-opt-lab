#!/usr/bin/env python3
"""Differential test: patched LCSSeq vs. the pristine upstream DP.

The reference below is a verbatim transcription of the *original*
``LCSSeq._dynamic`` body from upstream commit d6a68d6 (the numpy branch
replaced by a list-of-lists matrix, which computes the same integers).
Every case compares the returned subsequence **byte for byte**.
"""
from __future__ import annotations

import random

import pytest

import textdistance


def reference_lcs(seq1: str, seq2: str) -> str:
    lengths = [[0] * (len(seq2) + 1) for _ in range(len(seq1) + 1)]
    for i, char1 in enumerate(seq1):
        for j, char2 in enumerate(seq2):
            if char1 == char2:
                lengths[i + 1][j + 1] = lengths[i][j] + 1
            else:
                lengths[i + 1][j + 1] = max(lengths[i + 1][j], lengths[i][j + 1])
    result = ''
    i, j = len(seq1), len(seq2)
    while i != 0 and j != 0:
        if lengths[i][j] == lengths[i - 1][j]:
            i -= 1
        elif lengths[i][j] == lengths[i][j - 1]:
            j -= 1
        else:
            assert seq1[i - 1] == seq2[j - 1]
            result = seq1[i - 1] + result
            i -= 1
            j -= 1
    return result


ALPHABETS = [
    'ab',
    'abcde',
    'abcdefghijklmnopqrstuvwxyz',
    '0123456789',
    'aàäçéèêñöüß中文日本語한국어',
    'αβγδεζηθικλμνξοπρστυφχψω',
    '😀😃😄🙂🙃😉😊🎉🚀',
    'aA1 ,.;\n\t',
]


def _cases():
    rng = random.Random(20261031)
    cases = []
    # 1200 randomized pairs across 8 alphabets and mixed lengths.
    for k in range(1200):
        alpha = ALPHABETS[k % len(ALPHABETS)]
        n1 = rng.randint(0, 40)
        n2 = rng.randint(0, 40)
        a = ''.join(rng.choice(alpha) for _ in range(n1))
        b = ''.join(rng.choice(alpha) for _ in range(n2))
        cases.append((a, b))
    # boundary cases: empty, single element, extremes, no overlap, long runs.
    boundary = [
        ('', ''), ('', 'a'), ('a', ''), ('a', 'a'), ('a', 'b'),
        ('aaaa', 'aaaa'), ('aaaa', 'aa'), ('ab', 'ba'), ('abc', 'cba'),
        ('x' * 60, 'y' * 60), ('x' * 60, 'x' * 60),
        ('abcdefghij', 'jihgfedcba'), ('aabbaabb', 'bbaaaabb'),
        ('中文日本語', '日本語中文'), ('😀🚀🎉', '🎉🚀😀'),
        ('\n\t ,.;', ';., \t\n'), ('a' * 50 + 'b' * 50, 'b' * 50 + 'a' * 50),
    ]
    return cases + boundary


CASES = _cases()


def test_case_count():
    assert len(CASES) >= 1000


@pytest.mark.parametrize('a,b', CASES, ids=range(len(CASES)))
def test_byte_identical(a, b):
    got = textdistance.lcsseq(a, b)
    want = reference_lcs(a, b)
    assert got == want
    assert got.encode('utf-8') == want.encode('utf-8')
    # the similarity() wrapper must agree too
    assert textdistance.LCSSeq().similarity(a, b) == len(want)
