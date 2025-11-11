# scripts/machine_learning/evaluate_model.py (corrected version)

import os
import joblib
import torch
import numpy as np
import matplotlib.pyplot as plt
from sklearn.metrics import mean_squared_error, mean_absolute_error, r2_score
from scripts.machine_learning_training.model import LSTM_Model
from utils.logger import get_logger
from configs.config import TRAINING_DIR
from datetime import datetime

logger = get_logger("evaluation.py")

def evaluate_model_task(batch_size: int = 64, generate_plots: bool = True, **context):
    """
    Evaluate trained model on test set and generate performance visualizations.
    """
    ti = context["ti"]
    
    # Pull training artifacts from XCom (saved by 'train_model' task)
    artifacts_path = ti.xcom_pull(task_ids='train_model', key='training_artifacts_path')
    if not artifacts_path:
        raise ValueError("❌ No training artifacts path found in XCom. Check 'train_model' task.")
    
    logger.info(f"📂 Loading training artifacts from: {artifacts_path}")
    artifacts = joblib.load(artifacts_path)
    metadata = artifacts['metadata']
    
    # Get test data from artifacts (now properly saved)
    X_test = artifacts['X_test']
    Y_test = artifacts['Y_test']
    
    # Get base prices and time indices from metadata
    base_prices_test = metadata['base_prices_test']
    test_time_indices = metadata['test_time_indices']
    
    logger.info(f"✅ Loaded test data: X_test={X_test.shape}, Y_test={Y_test.shape}")
    
    # Reconstruct model
    device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
    logger.info(f"🚀 Using device for evaluation: {device}")
    
    input_size = X_test.shape[2]
    model = LSTM_Model(input_size=input_size).to(device)
    
    # Load best model weights
    model_path = artifacts['model_state_dict_path']
    model.load_state_dict(torch.load(model_path, map_location=device))
    model.eval()
    
    # Make predictions
    with torch.no_grad():
        X_test_tensor = torch.tensor(X_test, dtype=torch.float32).to(device)
        Y_pred = model(X_test_tensor).cpu().numpy().flatten()
    
    # Convert returns to prices if needed
    if metadata['predict_returns']:
        Y_pred_prices = base_prices_test * (1 + Y_pred)
        Y_test_prices = base_prices_test * (1 + Y_test)
        logger.info("✅ Converted predicted returns to absolute prices")
    else:
        Y_pred_prices = Y_pred
        Y_test_prices = Y_test
        logger.info("✅ Using absolute price predictions")
    
    # Calculate metrics
    mse = mean_squared_error(Y_test_prices, Y_pred_prices)
    rmse = np.sqrt(mse)
    mae = mean_absolute_error(Y_test_prices, Y_pred_prices)
    r2 = r2_score(Y_test_prices, Y_pred_prices)
    
    metrics = {
        'RMSE': rmse,
        'MAE': mae,
        'R2': r2,
        'Mean_Actual_Price': Y_test_prices.mean(),
        'Std_Actual_Price': Y_test_prices.std(),
        'Prediction_Mean': Y_pred_prices.mean(),
        'Prediction_Std': Y_pred_prices.std(),
        'Sample_Count': len(Y_test_prices)
    }
    
    logger.info(f"\n📊 TEST SET METRICS:")
    logger.info(f"RMSE: ${rmse:.4f}")
    logger.info(f"MAE: ${mae:.4f}")
    logger.info(f"R²: {r2:.4f}")
    logger.info(f"Mean Actual Price: ${Y_test_prices.mean():.4f}")
    logger.info(f"Std Actual Price: ${Y_test_prices.std():.4f}")
    logger.info(f"Number of Test Samples: {len(Y_test_prices):,}")
    
    # Create output directories
    eval_dir = os.path.join(TRAINING_DIR, "evaluation")
    plots_dir = os.path.join(eval_dir, "plots")
    os.makedirs(plots_dir, exist_ok=True)
    
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    
    # Generate and save plots
    plot_paths = {}
    if generate_plots:
        # 1. Loss curves plot
        plt.figure(figsize=(12, 6))
        plt.plot(artifacts['train_loss_history'], label='Training Loss', linewidth=2, color='blue')
        plt.plot(artifacts['val_loss_history'], label='Validation Loss', linewidth=2, color='orange')
        plt.title('Model Training Loss Curves', fontsize=16)
        plt.xlabel('Epoch', fontsize=14)
        plt.ylabel('Loss (MSE)', fontsize=14)
        plt.yscale('log')
        plt.grid(True, alpha=0.3)
        plt.legend(fontsize=12)
        plt.tight_layout()
        
        loss_plot_path = os.path.join(plots_dir, f"loss_curves_{timestamp}.png")
        plt.savefig(loss_plot_path, dpi=300, bbox_inches='tight')
        plt.close()
        plot_paths['loss_curves'] = loss_plot_path
        logger.info(f"📈 Saved loss curves plot to: {loss_plot_path}")
        
        # 2. Forecast visualization
        plt.figure(figsize=(16, 8))
        
        # Calculate confidence intervals (95%)
        errors = Y_test_prices - Y_pred_prices
        std_error = np.std(errors)
        ci_upper = Y_pred_prices + 1.96 * std_error
        ci_lower = Y_pred_prices - 1.96 * std_error
        
        # Plot actual prices
        plt.plot(test_time_indices, Y_test_prices, 
                 label="Actual Prices", color='blue', linewidth=2, alpha=0.8)
        
        # Plot predicted prices
        plt.plot(test_time_indices, Y_pred_prices, 
                 label="Predicted Prices", color='red', linewidth=2, alpha=0.8)
        
        # Plot confidence interval
        plt.fill_between(test_time_indices, ci_lower, ci_upper, 
                         color='red', alpha=0.15, label='95% Confidence Interval')
        
        # Highlight recent predictions
        recent_mask = np.arange(len(test_time_indices)) >= len(test_time_indices) - 24  # Last 24 periods
        if np.any(recent_mask):
            plt.scatter(np.array(test_time_indices)[recent_mask], 
                       Y_test_prices[recent_mask], 
                       color='green', s=50, zorder=5, label='Recent Actual')
            plt.scatter(np.array(test_time_indices)[recent_mask], 
                       Y_pred_prices[recent_mask], 
                       color='purple', s=50, zorder=5, label='Recent Predicted')
        
        plt.title('Model Forecast vs Actual Prices (Test Set)', fontsize=18)
        plt.xlabel('Time', fontsize=14)
        plt.ylabel('Price ($)', fontsize=14)
        plt.grid(True, alpha=0.3)
        plt.legend(loc='best', fontsize=12)
        plt.xticks(rotation=45)
        
        # Format y-axis as currency
        ax = plt.gca()
        ax.yaxis.set_major_formatter('${x:,.0f}')
        
        plt.tight_layout()
        
        forecast_plot_path = os.path.join(plots_dir, f"forecast_{timestamp}.png")
        plt.savefig(forecast_plot_path, dpi=300, bbox_inches='tight')
        plt.close()
        plot_paths['forecast'] = forecast_plot_path
        logger.info(f"📈 Saved forecast plot to: {forecast_plot_path}")
        
        # 3. Error distribution plot
        residuals = Y_test_prices - Y_pred_prices
        plt.figure(figsize=(12, 6))
        plt.hist(residuals, bins=50, alpha=0.7, color='purple', edgecolor='black')
        plt.axvline(x=np.mean(residuals), color='red', linestyle='--', 
                    label=f'Mean Error: ${np.mean(residuals):.2f}')
        plt.axvline(x=0, color='black', linestyle='-', alpha=0.3)
        plt.title('Prediction Error Distribution', fontsize=16)
        plt.xlabel('Error ($)', fontsize=14)
        plt.ylabel('Frequency', fontsize=14)
        plt.grid(True, alpha=0.3)
        plt.legend(fontsize=12)
        plt.tight_layout()
        
        error_plot_path = os.path.join(plots_dir, f"error_distribution_{timestamp}.png")
        plt.savefig(error_plot_path, dpi=300, bbox_inches='tight')
        plt.close()
        plot_paths['error_distribution'] = error_plot_path
        logger.info(f"📈 Saved error distribution plot to: {error_plot_path}")
    
    # Save evaluation results
    eval_results = {
        'metrics': metrics,
        'plot_paths': plot_paths,
        'model_path': model_path,
        'artifacts_path': artifacts_path,
        'timestamp': timestamp,
        'config': {
            'batch_size': batch_size,
            'generate_plots': generate_plots,
            'forecast_horizon': metadata.get('forecast_horizon', 12),
            'lookback_window': metadata.get('lookback_window', 120),
            'predict_returns': metadata.get('predict_returns', True)
        },
        # Save raw prediction data for further analysis
        'predictions': {
            'time_indices': test_time_indices,
            'actual_prices': Y_test_prices,
            'predicted_prices': Y_pred_prices,
            'errors': residuals if 'residuals' in locals() else None
        }
    }
    
    eval_results_path = os.path.join(eval_dir, f"evaluation_results_{timestamp}.joblib")
    joblib.dump(eval_results, eval_results_path)
    logger.info(f"💾 Saved comprehensive evaluation results to: {eval_results_path}")
    
    # Push evaluation results to XCom
    ti.xcom_push(key="evaluation_results_path", value=eval_results_path)
    ti.xcom_push(key="forecast_plot_path", value=plot_paths.get('forecast', ''))
    ti.xcom_push(key="loss_plot_path", value=plot_paths.get('loss_curves', ''))
    
    logger.info("✅ Model evaluation completed successfully!")
    return eval_results_path