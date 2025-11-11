import os
import joblib
import torch
import torch.nn as nn
from scripts.machine_learning_training.model import LSTM_Model
from datetime import datetime
from utils.logger import get_logger
from configs.config import TRAINING_DIR

logger = get_logger("training.py")


# ============================================================
# MODEL TRAINING LOOP
# ============================================================
def train_model(model, train_loader, val_loader, criterion, optimizer,
                scheduler, num_epochs=100, device=None):
    best_val_loss = float('inf')
    train_loss_history = []
    val_loss_history = []
    patience_counter = 0
    max_patience = 15

    for epoch in range(1, num_epochs + 1):
        model.train()
        train_losses = []

        for xb, yb in train_loader:
            xb, yb = xb.to(device), yb.to(device)
            optimizer.zero_grad()
            preds = model(xb)
            loss = criterion(preds, yb)
            loss.backward()
            optimizer.step()
            train_losses.append(loss.item())

        train_loss = sum(train_losses) / len(train_losses)
        train_loss_history.append(train_loss)

        # Validation
        model.eval()
        val_losses = []
        with torch.no_grad():
            for xb, yb in val_loader:
                xb, yb = xb.to(device), yb.to(device)
                preds = model(xb)
                loss = criterion(preds, yb)
                val_losses.append(loss.item())

        val_loss = sum(val_losses) / len(val_losses)
        val_loss_history.append(val_loss)
        scheduler.step(val_loss)

        logger.info(f"Epoch {epoch}/{num_epochs}, train_loss={train_loss:.6f}, val_loss={val_loss:.6f}")

        if val_loss < best_val_loss:
            best_val_loss = val_loss
            patience_counter = 0
            # Save best model to TRAINING_DIR/model (not current dir)
            model_path = os.path.join(TRAINING_DIR, "model", "best_model_regression.pth")
            os.makedirs(os.path.dirname(model_path), exist_ok=True)
            torch.save(model.state_dict(), model_path)
            logger.info(f"  📦 Saved best model to {model_path}")
        else:
            patience_counter += 1
            if patience_counter >= max_patience:
                logger.info(f"Early stopping after {epoch} epochs")
                break

    return model, train_loss_history, val_loss_history


# ============================================================
# TRAINING PIPELINE
# ============================================================
def training_pipeline(
    X_train, X_test, Y_train, Y_test,
    num_epochs=100,
    learning_rate=0.0005,
    weight_decay=1e-5,
    batch_size=64,
    device=None
):
    input_size = X_train.shape[2]
    model = LSTM_Model(input_size=input_size).to(device)
    criterion = nn.MSELoss()

    train_dataset = torch.utils.data.TensorDataset(
        torch.tensor(X_train, dtype=torch.float32),
        torch.tensor(Y_train, dtype=torch.float32)
    )
    train_loader = torch.utils.data.DataLoader(train_dataset, batch_size=batch_size, shuffle=True)

    val_dataset = torch.utils.data.TensorDataset(
        torch.tensor(X_test, dtype=torch.float32),
        torch.tensor(Y_test, dtype=torch.float32)
    )
    val_loader = torch.utils.data.DataLoader(val_dataset, batch_size=batch_size, shuffle=False)

    optimizer = torch.optim.Adam(
        model.parameters(),
        lr=learning_rate,
        weight_decay=weight_decay
    )

    scheduler = torch.optim.lr_scheduler.ReduceLROnPlateau(
        optimizer, mode='min', patience=3, factor=0.7, min_lr=1e-6
    )

    model, train_hist, val_hist = train_model(
        model, train_loader, val_loader, criterion,
        optimizer, scheduler, num_epochs=num_epochs, device=device
    )

    return model, train_hist, val_hist


# ============================================================
# AIRFLOW ENTRY POINT — uses XCom + op_kwargs
# ============================================================
def train_model_task(
    num_epochs: int = 25,
    learning_rate: float = 0.0001,
    weight_decay: float = 1e-5,
    batch_size: int = 64,
    **context
):
    """
    Airflow task: Train an LSTM model using data prepared in the previous step.

    - Saves timestamped artifacts:  training_artifacts_YYYYMMDD_HHMMSS.joblib
    - Also updates 'training_artifacts_latest.joblib' symlink or copy.
    - Pushes model + artifact paths to XCom.
    """
    import os
    import joblib
    import torch
    import shutil
    from datetime import datetime
    from scripts.machine_learning_training.model import LSTM_Model
    from utils.logger import get_logger
    from configs.config import TRAINING_DIR
    from scripts.machine_learning_training.training import training_pipeline

    logger = get_logger("train_model_task")
    ti = context["ti"]

    # ----------------------------------------------------------------------
    # Step 1. Pull preprocessed training data
    # ----------------------------------------------------------------------
    joblib_path = ti.xcom_pull(task_ids='prepare_training_data', key='training_data_path')
    if not joblib_path:
        raise ValueError("❌ No training data path found in XCom. Check 'prepare_training_data' task.")

    logger.info(f"📂 Loading training data from: {joblib_path}")
    data = joblib.load(joblib_path)

    X_train = data['X_train']
    X_test = data['X_test']
    Y_train = data['Y_train']
    Y_test = data['Y_test']
    metadata = data['metadata']

    device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
    logger.info(f"🚀 Using device: {device}")

    # ----------------------------------------------------------------------
    # Step 2. Train model
    # ----------------------------------------------------------------------
    model, train_hist, val_hist = training_pipeline(
        X_train=X_train,
        X_test=X_test,
        Y_train=Y_train,
        Y_test=Y_test,
        num_epochs=num_epochs,
        learning_rate=learning_rate,
        weight_decay=weight_decay,
        batch_size=batch_size,
        device=device
    )

    # ----------------------------------------------------------------------
    # Step 3. Save timestamped artifacts
    # ----------------------------------------------------------------------
    os.makedirs(os.path.join(TRAINING_DIR, "model"), exist_ok=True)

    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    best_model_path = os.path.join(TRAINING_DIR, "model", "best_model_regression.pth")
    artifact_path = os.path.join(TRAINING_DIR, "model", f"training_artifacts_{timestamp}.joblib")

    joblib.dump({
        'model_state_dict_path': best_model_path,
        'train_loss_history': train_hist,
        'val_loss_history': val_hist,
        'X_test': X_test,
        'Y_test': Y_test,
        'metadata': metadata,
        'config': {
            'num_epochs': num_epochs,
            'learning_rate': learning_rate,
            'weight_decay': weight_decay,
            'batch_size': batch_size,
            'input_size': X_train.shape[2],
            'lookback_window': metadata.get('lookback_window'),
        }
    }, artifact_path)

    logger.info(f"💾 Saved training artifacts WITH TEST DATA to: {artifact_path}")

    # ----------------------------------------------------------------------
    # Step 4. Maintain 'latest' symlink or copy
    # ----------------------------------------------------------------------
    latest_artifact = os.path.join(TRAINING_DIR, "model", "training_artifacts_latest.joblib")
    try:
        if os.path.exists(latest_artifact):
            os.remove(latest_artifact)
        os.symlink(artifact_path, latest_artifact)
        logger.info(f"🔗 Updated symlink: {latest_artifact} → {artifact_path}")
    except (AttributeError, OSError):
        shutil.copy2(artifact_path, latest_artifact)
        logger.info(f"📄 Copied latest artifact to {latest_artifact}")

    # ----------------------------------------------------------------------
    # Step 5. Push paths to XCom
    # ----------------------------------------------------------------------
    ti.xcom_push(key="final_model_path", value=best_model_path)
    ti.xcom_push(key="training_artifacts_path", value=artifact_path)
    ti.xcom_push(key="training_artifacts_latest", value=latest_artifact)

    logger.info("📤 XCom pushed with final model and artifact paths.")
    return artifact_path