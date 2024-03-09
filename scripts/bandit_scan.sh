#! /bin/bash
`cd ../`
out_file=bandit_report.txt
src_path=src/
pyproject_file=pyproject.toml
bandit --recursive --severity-level all --output $out_file --format txt $src_path ; echo "" >> $out_file ; echo "myt-cli app version for bandit run is:" >> $out_file ; grep "^version = " $pyproject_file >> $out_file