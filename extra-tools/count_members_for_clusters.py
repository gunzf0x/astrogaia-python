import os
from pathlib import Path

def count_lines_in_file(file_path):
    with open(file_path, 'r') as file:
        line_count = sum(1 for line in file if not line.startswith('#'))
    return line_count-1

def count_lines_in_files(directory_path):
    counter_open_clusters, counter_globular_clusters = 0, 0
    for root, _ , files in os.walk(directory_path):
        for file in files:
            if file.endswith("_filter_cordoni.dat"):
                file_path = os.path.join(root, file)
                line_count = count_lines_in_file(file_path)
                name = str(Path(file_path).parent.name)
                print(f"{name}: {line_count} lines")
                if "globularcluster" in file_path.lower():
                    counter_globular_clusters += 1
                if "opencluster" in file_path.lower():
                    counter_open_clusters +=1
    print("="*50)
    print(f"Globular Clusters: {counter_globular_clusters}")
    print(f"Open Clusters: {counter_open_clusters}")


# Usage example
directory_path = '../Objects'
count_lines_in_files(directory_path)
