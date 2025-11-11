import sys
import time
import os
from datetime import timedelta

# Direct function imports instead of subprocess calls
from scripts.price.init_historical_price import init_historical_price
from scripts.price.load_price import load_price
from scripts.price.create_aggregates import create_aggregate
from scripts.price.backfill_price import backfill_price

from configs.config import PARQUET_PATH, AGGREGATES_DIR

# ✅ List of aggregate scripts to execute
sql_dir = "schema/aggregates"

AGGREGATE_SCRIPTS = [   
    f
    for f in sorted(os.listdir(sql_dir))
    if f.endswith(".sql")
]

# ----------------------------------------------------------------------
# 🧹 Utility Functions
# ----------------------------------------------------------------------
def delete_parquet_file():
    """Remove the existing Parquet file before each full pipeline run."""
    if os.path.exists(PARQUET_PATH):
        os.remove(PARQUET_PATH)
        print(f"🗑️ Deleted {PARQUET_PATH}")
    else:
        print("⚠️ No Parquet file found to delete — skipping.")


def run_function(func, func_name, **kwargs):
    """Run a single ETL function and measure its execution time."""
    print(f"\n=== 🚀 Running {func_name} ===")
    start_time = time.time()
    try:
        result = func(**kwargs)
        duration = time.time() - start_time
        print(f"✅ Finished {func_name} in {timedelta(seconds=duration)}")
        print(f"   Result: {result}")
        return duration, result
    except Exception as e:
        duration = time.time() - start_time
        print(f"❌ Error in {func_name} after {timedelta(seconds=duration)}: {e}")
        raise


def run_pipeline():
    """Run the full ETL pipeline sequentially."""
    total_start = time.time()
    
    # Step 1: Download historical data from Kaggle
    run_function(init_historical_price, "init_historical_price")
    
    # Step 2: Load data into TimescaleDB
    run_function(load_price, "load_price")
    
    # Step 3: Create continuous aggregates in parallel
    print(f"\n=== 🚀 Running create_aggregates in parallel ===")
    aggregate_start = time.time()
    
    # Prepare list of valid script paths
    valid_scripts = []
    for script in AGGREGATE_SCRIPTS:
        script_path = os.path.join(AGGREGATES_DIR, script)
        if os.path.exists(script_path):
            valid_scripts.append(script)
        else:
            print(f"⚠️ Aggregate script not found: {script_path}")
    
    # Execute all valid aggregate scripts in parallel
    import concurrent.futures

    def execute_aggregate_script(script_name):
        """Wrapper to run a single aggregate script."""
        script_path = os.path.join(AGGREGATES_DIR, script_name)
        print(f"   🔄 Executing {script_name}...")
        result = create_aggregate(script_name=script_name)  # Pass only filename
        return script_name, result

    # Run all valid scripts in parallel
    with concurrent.futures.ThreadPoolExecutor(max_workers=4) as executor:
        # Submit all tasks
        futures = {
            executor.submit(execute_aggregate_script, script): script
            for script in valid_scripts
        }

        # Collect results as they complete
        for future in concurrent.futures.as_completed(futures):
            script_name = futures[future]
            try:
                result = future.result()
                print(f"   ✅ {script_name} completed: {result}")
            except Exception as e:
                print(f"   ❌ {script_name} failed: {e}")

    aggregate_duration = time.time() - aggregate_start
    print(f"✅ All aggregates completed in {timedelta(seconds=aggregate_duration)}")
    
    # Step 4: Update with latest data from Bitstamp API
    run_function(
        backfill_price, 
        "update_historical_price",
        currency_pair="btcusd",
        parquet_filename=PARQUET_PATH
    )
    
    total_duration = time.time() - total_start
    print(f"\n🎯 Pipeline completed in {timedelta(seconds=total_duration)}")
    return total_duration


# ----------------------------------------------------------------------
# 🧪 Individual Function Tests
# ----------------------------------------------------------------------
def test_individual_functions():
    """Test each function individually with various scenarios."""
    print("\n" + "="*60)
    print("🧪 INDIVIDUAL FUNCTION TESTS")
    print("="*60)
    
    # Test 1: Init Historical Price (with existing file)
    print("\n--- Test 1: init_historical_price (file exists) ---")
    try:
        result = init_historical_price()
        print(f"✅ Test passed: {result}")
    except Exception as e:
        print(f"❌ Test failed: {e}")
    
    # Test 2: Update Historical Price
    print("\n--- Test 2: update_historical_price ---")
    try:
        result = backfill_price(currency_pair="btcusd")
        print(f"✅ Test passed: {result}")
    except Exception as e:
        print(f"❌ Test failed: {e}")
    
    # Test 3: Load Price (requires DB connection)
    print("\n--- Test 3: load_price ---")
    try:
        result = load_price(parquet_path=PARQUET_PATH)
        print(f"✅ Test passed: {result}")
    except Exception as e:
        print(f"❌ Test failed: {e}")
    
    # Test 4: Create Aggregate
    if AGGREGATE_SCRIPTS:
        print(f"\n--- Test 4: create_aggregate ({AGGREGATE_SCRIPTS[0]}) ---")
        try:
            result = create_aggregate(script_name=AGGREGATE_SCRIPTS[0])
            print(f"✅ Test passed: {result}")
        except Exception as e:
            print(f"❌ Test failed: {e}")


# ----------------------------------------------------------------------
# 🧭 Main Orchestrator
# ----------------------------------------------------------------------
def main():
    """Main test orchestrator with multiple run modes."""
    
    # Configuration
    TEST_MODE = "full_pipeline"  # Options: "full_pipeline", "individual", "benchmark"
    NUM_BENCHMARK_RUNS = 3
    
    if TEST_MODE == "individual":
        # Run individual function tests
        test_individual_functions()
        
    elif TEST_MODE == "benchmark":
        # Run multiple pipeline iterations for benchmarking
        durations = []
        
        for i in range(1, NUM_BENCHMARK_RUNS + 1):
            print(f"\n{'='*60}")
            print(f"🏁 Starting pipeline run {i}/{NUM_BENCHMARK_RUNS}")
            print(f"{'='*60}")
            
            # Delete existing parquet file for a clean start
            delete_parquet_file()
            
            try:
                run_time = run_pipeline()
                durations.append(run_time)
            except Exception as e:
                print(f"❌ Pipeline run {i} failed: {e}")
                break
        
        # Print benchmark summary
        print("\n📊 PIPELINE PERFORMANCE SUMMARY")
        print("="*60)
        for idx, d in enumerate(durations, start=1):
            print(f"Run {idx}: {timedelta(seconds=d)}")
        
        if durations:
            avg_time = sum(durations) / len(durations)
            min_time = min(durations)
            max_time = max(durations)
            print(f"\n🏆 Average runtime: {timedelta(seconds=avg_time)}")
            print(f"⚡ Fastest run: {timedelta(seconds=min_time)}")
            print(f"🐌 Slowest run: {timedelta(seconds=max_time)}")
    
    else:  # full_pipeline
        # Single pipeline run
        print(f"\n{'='*60}")
        print("🏁 Starting single pipeline run")
        print(f"{'='*60}")
        
        try:
            run_time = run_pipeline()
            print(f"\n🎉 Pipeline completed successfully in {timedelta(seconds=run_time)}")
        except Exception as e:
            print(f"\n❌ Pipeline failed: {e}")
            sys.exit(1)


if __name__ == "__main__":
    main()