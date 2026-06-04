docker build -t provena-mcp .
docker run --rm -p 5000:5000 -e PROVENA_INSTANCE=dev.provena.nbic.cloud provena-mcp
