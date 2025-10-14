import pandas as pd

def parquet_to_csv(parquet_file, csv_file):
    """
    Convert a Parquet file to CSV format.
    
    Parameters:
    parquet_file (str): Path to input Parquet file
    csv_file (str): Path for output CSV file
    """
    # Read Parquet file into DataFrame
    df = pd.read_parquet(parquet_file)
    
    # Write DataFrame to CSV
    df.to_csv(csv_file, index=False)
    
    print(f"Successfully converted {parquet_file} to {csv_file}")

# Example usage
if __name__ == "__main__":
    # Replace these with your actual file paths
    input_parquet = "historical_data/btcusd_1-min_data.parquet"
    output_csv = "historical_data/btcusd_1-min_data.csv"
    
    parquet_to_csv(input_parquet, output_csv)