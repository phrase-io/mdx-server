# -*- coding: utf-8 -*-
# version: python 3.x

import sys

try:
    from pattern.en import lemma as pattern_lemma
except Exception:
    pattern_lemma = None


def main():
    if len(sys.argv) < 2:
        print("lemma.py word")
        return
    word = sys.argv[1]
    if pattern_lemma is None:
        print(word)
        return
    try:
        print(pattern_lemma(word))
    except Exception:
        print(word)


if __name__ == "__main__":
    main()
