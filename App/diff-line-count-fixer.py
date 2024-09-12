import re
import sys

def fix_diff_line_counts(file_path):
    with open(file_path, 'r') as file:
        content = file.read()

    # Regular expression to match hunk headers
    hunk_pattern = re.compile(r'@@ -(\d+),(\d+) \+(\d+),(\d+) @@')

    def count_lines(hunk):
        hunk_lines = hunk.split('\n')
        old_lines = len([line for line in hunk_lines if not line.startswith('+')])
        new_lines = len([line for line in hunk_lines if not line.startswith('-')])

        """
        print(f"*** HUNK")
        total_lines = 0
        old_lines = 0
        new_lines = 0
        for l in hunk_lines:
            total_lines += 1
            if not l.startswith('+'):
                old_lines += 1
            if not l.startswith('-'):
                new_lines += 1            
            print(f"total_lines={total_lines} old_lines={old_lines} new_lines={new_lines} {repr(l)}  ")
        """
        return old_lines - 1, new_lines - 1  # Subtract 1 to exclude the hunk header

    def fix_hunk(match):
        hunk_start = match.start()
        hunk_end = content.find('\n@@', hunk_start + 1)
        if hunk_end == -1:
            hunk_end = len(content)
        hunk = content[hunk_start:hunk_end]

        old_start, old_count, new_start, new_count = map(int, match.groups())
        actual_old_count, actual_new_count = count_lines(hunk)

        # :( SILLY HACK
        if hunk_end == len(content):
            actual_old_count -= 1
            actual_new_count -= 1

        if old_count != actual_old_count or new_count != actual_new_count:
            return f'@@ -{old_start},{actual_old_count} +{new_start},{actual_new_count} @@'
        return match.group()

    fixed_content = hunk_pattern.sub(fix_hunk, content)

    with open(file_path, 'w') as file:
        file.write(fixed_content)

    print(f"Processed {file_path}. Any incorrect hunk headers have been fixed.")

if __name__ == "__main__":
    if len(sys.argv) != 2:
        print("Usage: python fix_diff_line_counts.py <path_to_diff_file>")
        sys.exit(1)

    diff_file_path = sys.argv[1]
    fix_diff_line_counts(diff_file_path)
