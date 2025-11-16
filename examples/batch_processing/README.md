# Batch Processing with RAXE

Efficiently scan large volumes of prompts using parallel processing.

## Features

- Parallel scanning with ThreadPoolExecutor
- CSV input/output
- Progress tracking with tqdm
- Summary statistics
- Metadata preservation

## Usage

```bash
# Basic usage
python batch_scan.py input.csv output.csv

# Specify text column
python batch_scan.py data.csv results.csv message
```

## Input Format

CSV with at least one text column:

```csv
id,text,user_id
1,Hello world,user123
2,Suspicious message,user456
```

## Output Format

Original columns plus scan results:

```csv
id,text,has_threats,severity,detections_count,scan_time_ms,user_id
1,Hello world,False,NONE,0,2.3,user123
2,Suspicious message,True,HIGH,2,3.1,user456
```

## Performance

- Default: 10 parallel workers
- ~100 scans/second on typical hardware
- Adjust `max_workers` for your system

## Learn More

[RAXE Documentation](https://docs.raxe.ai)
