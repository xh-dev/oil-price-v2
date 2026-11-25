image_name=$1
oil-price-v2 fetch
oil-price-v2 decode --provider ollama --model qwen3.6:35b-mlx-cust
oil-price-v2 gen-html
oil-price-v2 gen-dockerfile
sudo docker build -t $image_name .
sudo docker push $image_name
