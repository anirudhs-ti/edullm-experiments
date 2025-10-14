#!/usr/bin/env python3
from match_curriculum_hybrid_grade3 import main as _base_main
import os

if __name__ == "__main__":
    os.environ["TARGET_GRADE_OVERRIDE"] = "6"
    _base_main()





