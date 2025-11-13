# Use the official Python image from the Docker Hub
FROM python:3.11-slim

# Set the working directory in the container
WORKDIR /app

# Install OpenJDK for JayDeBeApi
RUN apt-get update && \
    apt-get install -y --no-install-recommends openjdk-17-jre-headless && \
    apt-get clean && \
    rm -rf /var/lib/apt/lists/*

# Copy the requirements file into the container
COPY requirements.txt .

# Install the dependencies specified in the requirements file
RUN pip install --no-cache-dir -r requirements.txt

# Copy the current directory contents into the container at /app
COPY src/ /app/src
COPY drivers/ /app/drivers

# Set environment variables for Tibero (these can be overwritten with `docker run -e`)
ENV TIBERO_HOST=host.docker.internal
ENV TIBERO_PORT=8629
ENV TIBERO_SID=tibero
ENV TIBERO_USER=your_username
ENV TIBERO_PASSWORD=your_password
ENV PYTHONPATH=/app/src
ENV CLASSPATH=/app/drivers/tibero6-jdbc.jar

# Command to run the server
CMD ["python", "-m", "tibero_mcp_server.server"]
