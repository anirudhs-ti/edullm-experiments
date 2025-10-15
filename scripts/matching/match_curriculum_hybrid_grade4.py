#!/usr/bin/env python3
from match_curriculum_hybrid_grade3 import main as _base_main
import sys

if __name__ == "__main__":
    # Reuse grade3 logic by importing and running with grade override via env
    import os
    os.environ["TARGET_GRADE_OVERRIDE"] = "4"
    _base_main()







