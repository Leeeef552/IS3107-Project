# Use the official Airflow image as a base
FROM apache/airflow:2.9.0

# Switch to airflow user for safe pip install
USER airflow

# Copy requirements.txt into the image
COPY requirements.txt /opt/airflow/requirements.txt

# Install your dependencies as the airflow user
RUN pip install --no-cache-dir -r /opt/airflow/requirements.txt