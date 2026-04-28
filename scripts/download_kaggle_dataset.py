import os
import shutil
from pathlib import Path

import kagglehub

ROOT = Path(__file__).resolve().parents[1]
DATA_DIR = ROOT / 'data'
TARGET_PATH = DATA_DIR / 'dataset.csv'
KAGGLE_HANDLE = 'semustafacevik/software-defect-prediction'
PREFERRED_FILES = ('jm1.csv', 'jm1.arff')


def main():
    DATA_DIR.mkdir(parents=True, exist_ok=True)

    print(f'Downloading Kaggle dataset: {KAGGLE_HANDLE}')
    dataset_dir = Path(kagglehub.dataset_download(KAGGLE_HANDLE))
    print(f'Dataset cache: {dataset_dir}')

    source_path = None
    for preferred in PREFERRED_FILES:
        candidate = dataset_dir / preferred
        if candidate.exists():
            source_path = candidate
            break

    if source_path is None:
        csv_files = list(dataset_dir.rglob('*.csv'))
        if csv_files:
            source_path = csv_files[0]

    if source_path is None:
        raise FileNotFoundError('No CSV file found in the downloaded Kaggle dataset.')

    shutil.copy2(source_path, TARGET_PATH)
    print(f'Copied {source_path.name} to {TARGET_PATH}')


if __name__ == '__main__':
    main()
