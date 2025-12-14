"""Golden File Tests - Regression Prevention

Golden files prevent unintended changes to detection logic.

When detection logic changes:
    1. Tests will fail showing the diff
    2. Review the changes
    3. Update golden files if intentional:
       pytest tests/golden --update-golden

Structure:
    fixtures/
        input_001.txt      - Test input
        expected_001.json  - Expected output
"""
