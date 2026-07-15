# Start from an official, slim Python base image matching the Python
# version we've been developing with. "slim" keeps the image smaller than
# the full default image, which matters for build/deploy speed later.
FROM python:3.12-slim

# All subsequent commands run from this directory inside the container.
WORKDIR /app

# Copy just the requirements file first (before the rest of the code).
# Docker caches each step - if only your code changes later but not your
# dependencies, this lets Docker skip re-installing everything from scratch.
COPY requirements.txt .

RUN pip install --no-cache-dir -r requirements.txt

# Now copy the rest of the project files into the image.
COPY . .

# Build the vector index inside the image at build time, so the container
# starts up already ready to serve requests, rather than building the
# index on every startup.
RUN python3 build_index.py

# Document that the container listens on port 8000 (informational - the
# actual port mapping happens when we run the container).
EXPOSE 8000

# The command that runs when the container starts: launch the API with
# uvicorn, listening on all network interfaces (0.0.0.0) so it's reachable
# from outside the container, not just from within it.
CMD ["uvicorn", "api:app", "--host", "0.0.0.0", "--port", "8000"]
