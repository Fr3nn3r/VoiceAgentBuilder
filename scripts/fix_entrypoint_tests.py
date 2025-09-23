"""Script to fix all entrypoint tests by adding job context patch"""

import re

# Read the test file
with open('tests/unit/test_entrypoint.py', 'r') as f:
    content = f.read()

# Pattern to find test methods that need fixing
# We need to add the job context patch to all test methods that use MultilingualModel
pattern = r"(with patch\('livekit\.plugins\.turn_detector\.multilingual\.MultilingualModel'\) as mock_turn:\s*\n\s*with patch\('livekit\.plugins\.noise_cancellation\.BVC'\) as mock_noise:)"

# Replacement that adds the job context patch
replacement = r"\1\n                                        with patch('livekit.agents.job.get_job_context', return_value=mock_job_context):"

# Apply the replacement
content = re.sub(pattern, replacement, content)

# Now we need to fix the indentation of the code inside each test
# Find all blocks that start after our new patch and indent them properly
pattern2 = r"(with patch\('livekit\.agents\.job\.get_job_context', return_value=mock_job_context\):)\n(\s{40})(\S)"
replacement2 = r"\1\n\2    \3"

content = re.sub(pattern2, replacement2, content, flags=re.MULTILINE)

# Write back the fixed content
with open('tests/unit/test_entrypoint.py', 'w') as f:
    f.write(content)

print("Fixed all entrypoint tests")