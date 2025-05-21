#!/bin/bash

# Function to detect GPU type
detect_gpu_type() {
    # Check if nvidia-smi is available
    if ! command -v nvidia-smi &> /dev/null; then
        echo "Error: nvidia-smi not found. NVIDIA GPU drivers may not be installed."
        exit 1
    fi

    # Run nvidia-smi -L to get GPU information
    GPU_INFO=$(nvidia-smi -L)
    
    # Check if any GPU was detected
    if [ -z "$GPU_INFO" ]; then
        echo "Error: No NVIDIA GPUs detected."
        exit 1
    fi
    
    # Check for specific GPU models
    if echo "$GPU_INFO" | grep -i "V100" &> /dev/null; then
        echo "v100"
    elif echo "$GPU_INFO" | grep -i "A100" &> /dev/null; then
        echo "a100"
    elif echo "$GPU_INFO" | grep -i "H100" &> /dev/null; then
        echo "h100"
    else
        # Default to qwq for other GPU types
        echo "qwq"
    fi
}

# Check if a GPU type was manually specified (for override capability)
if [ $# -eq 1 ]; then
    GPU_TYPE=$(echo "$1" | tr '[:upper:]' '[:lower:]')  # Convert to lowercase
    
    # Validate GPU type
    if [[ "$GPU_TYPE" != "v100" && "$GPU_TYPE" != "a100" && "$GPU_TYPE" != "h100" && "$GPU_TYPE" != "qwq" && "$GPU_TYPE" != "image" ]]; then
        echo "Unsupported GPU type: $GPU_TYPE"
        echo "Supported GPU types: v100, a100, h100, qwq"
        exit 1
    fi
    
    echo "Using manually specified GPU type: $GPU_TYPE"
else
    # Auto-detect GPU type
    GPU_TYPE=$(detect_gpu_type)
    echo "Detected GPU type: $GPU_TYPE"
fi

# Load Python module
echo 'module load python/gpu/3.11.5'
module load python/gpu/3.11.5

export GIN_MODE=release
# Configure based on GPU type
case "$GPU_TYPE" in
    "v100")
        echo "Configuring for V100 GPUs..."
		export OLLAMA_MODELS=/N/project/fads_ng/ollama_setup/ollama_models
        export OLLAMA_MAX_LOADED_MODELS=12
        
        # GPU 0
        export CUDA_VISIBLE_DEVICES=0
        export OLLAMA_HOST="127.0.0.1:11434"
        ollama serve &
        export OLLAMA_HOST="127.0.0.1:11435"
        ollama serve &
        export OLLAMA_HOST="127.0.0.1:11436"
        ollama serve &
        
        # GPU 1
        export CUDA_VISIBLE_DEVICES=1
        export OLLAMA_HOST="127.0.0.1:11437"
        ollama serve &
        export OLLAMA_HOST="127.0.0.1:11438"
        ollama serve &
        export OLLAMA_HOST="127.0.0.1:11439"
        ollama serve &
        
        # GPU 2
        export CUDA_VISIBLE_DEVICES=2
        export OLLAMA_HOST="127.0.0.1:11440"
        ollama serve &
        export OLLAMA_HOST="127.0.0.1:11441"
        ollama serve &
        export OLLAMA_HOST="127.0.0.1:11442"
        ollama serve &
        
        # GPU 3
        export CUDA_VISIBLE_DEVICES=3
        export OLLAMA_HOST="127.0.0.1:11443"
        ollama serve &
        export OLLAMA_HOST="127.0.0.1:11444"
        ollama serve &
        export OLLAMA_HOST="127.0.0.1:11445"
        ollama serve &
        ;;
        
    "a100")
        echo "Configuring for A100 GPUs..."
		export OLLAMA_MODELS=/N/project/fads_ng/ollama_setup/ollama_models
        export OLLAMA_MAX_LOADED_MODELS=16
        
        # GPU 0
        export CUDA_VISIBLE_DEVICES=0
        export OLLAMA_HOST="127.0.0.1:11434"
        ollama serve &
        export OLLAMA_HOST="127.0.0.1:11435"
        ollama serve &
        export OLLAMA_HOST="127.0.0.1:11436"
        ollama serve &
        export OLLAMA_HOST="127.0.0.1:11437"
        ollama serve &
        
        # GPU 1
        export CUDA_VISIBLE_DEVICES=1
        export OLLAMA_HOST="127.0.0.1:11438"
        ollama serve &
        export OLLAMA_HOST="127.0.0.1:11439"
        ollama serve &
        export OLLAMA_HOST="127.0.0.1:11440"
        ollama serve &
        export OLLAMA_HOST="127.0.0.1:11441"
        ollama serve &
        
        # GPU 2
        export CUDA_VISIBLE_DEVICES=2
        export OLLAMA_HOST="127.0.0.1:11442"
        ollama serve &
        export OLLAMA_HOST="127.0.0.1:11443"
        ollama serve &
        export OLLAMA_HOST="127.0.0.1:11444"
        ollama serve &
        export OLLAMA_HOST="127.0.0.1:11445"
        ollama serve &
        
        # GPU 3
        export CUDA_VISIBLE_DEVICES=3
        export OLLAMA_HOST="127.0.0.1:11446"
        ollama serve &
        export OLLAMA_HOST="127.0.0.1:11447"
        ollama serve &
        export OLLAMA_HOST="127.0.0.1:11448"
        ollama serve &
        export OLLAMA_HOST="127.0.0.1:11449"
        ollama serve &
        ;;
        
    "h100")
        echo "Configuring for H100 GPUs..."
		export OLLAMA_MODELS=/N/project/fads_ng/ollama_setup/ollama_models
        export OLLAMA_MAX_LOADED_MODELS=32
        
        # GPU 0 (all instances on a single GPU)
        export CUDA_VISIBLE_DEVICES=0
        export OLLAMA_HOST="127.0.0.1:11434"
        ollama serve &
        export OLLAMA_HOST="127.0.0.1:11435"
        ollama serve &
        export OLLAMA_HOST="127.0.0.1:11436"
        ollama serve &
        export OLLAMA_HOST="127.0.0.1:11437"
        ollama serve &
        export OLLAMA_HOST="127.0.0.1:11438"
        ollama serve &
        export OLLAMA_HOST="127.0.0.1:11439"
        ollama serve &
        export OLLAMA_HOST="127.0.0.1:11440"
        ollama serve &
        export OLLAMA_HOST="127.0.0.1:11441"
        ollama serve &

		export CUDA_VISIBLE_DEVICES=1
        export OLLAMA_HOST="127.0.0.1:11442"
        ollama serve &
        export OLLAMA_HOST="127.0.0.1:11443"
        ollama serve &
        export OLLAMA_HOST="127.0.0.1:11444"
        ollama serve &
        export OLLAMA_HOST="127.0.0.1:11445"
        ollama serve &
        export OLLAMA_HOST="127.0.0.1:11446"
        ollama serve &
        export OLLAMA_HOST="127.0.0.1:11447"
        ollama serve &
        export OLLAMA_HOST="127.0.0.1:11448"
        ollama serve &
        export OLLAMA_HOST="127.0.0.1:11449"
        ollama serve &

        export CUDA_VISIBLE_DEVICES=2
        export OLLAMA_HOST="127.0.0.1:11450"
        ollama serve &
        export OLLAMA_HOST="127.0.0.1:11451"
        ollama serve &
        export OLLAMA_HOST="127.0.0.1:11452"
        ollama serve &
        export OLLAMA_HOST="127.0.0.1:11453"
        ollama serve &
        export OLLAMA_HOST="127.0.0.1:11454"
        ollama serve &
        export OLLAMA_HOST="127.0.0.1:11455"
        ollama serve &
        export OLLAMA_HOST="127.0.0.1:11456"
        ollama serve &
        export OLLAMA_HOST="127.0.0.1:11457"
        ollama serve &

        export CUDA_VISIBLE_DEVICES=3
        export OLLAMA_HOST="127.0.0.1:11458"
        ollama serve &
        export OLLAMA_HOST="127.0.0.1:11459"
        ollama serve &
        export OLLAMA_HOST="127.0.0.1:11460"
        ollama serve &
        export OLLAMA_HOST="127.0.0.1:11461"
        ollama serve &
        export OLLAMA_HOST="127.0.0.1:11462"
        ollama serve &
        export OLLAMA_HOST="127.0.0.1:11463"
        ollama serve &
        export OLLAMA_HOST="127.0.0.1:11464"
        ollama serve &
        export OLLAMA_HOST="127.0.0.1:11465"
        ollama serve &
        ;;
        
    "qwq")
        echo "Configuring for QWQ GPUs..."
        export OLLAMA_MODELS=/N/project/fads_ng/ollama_setup/ollama_models
        export OLLAMA_MAX_LOADED_MODELS=8
        
        # GPU 0
        export CUDA_VISIBLE_DEVICES=0
        export OLLAMA_HOST="127.0.0.1:11434"
        ollama serve &
        export OLLAMA_HOST="127.0.0.1:11435"
        ollama serve &
        
        # GPU 1
        export CUDA_VISIBLE_DEVICES=1
        export OLLAMA_HOST="127.0.0.1:11436"
        ollama serve &
        export OLLAMA_HOST="127.0.0.1:11437"
        ollama serve &
        
        # GPU 2
        export CUDA_VISIBLE_DEVICES=2
        export OLLAMA_HOST="127.0.0.1:11438"
        ollama serve &
        export OLLAMA_HOST="127.0.0.1:11439"
        ollama serve &
        
        # GPU 3
        export CUDA_VISIBLE_DEVICES=3
        export OLLAMA_HOST="127.0.0.1:11440"
        ollama serve &
        export OLLAMA_HOST="127.0.0.1:11441"
        ollama serve &
        ;;
    "image")
        echo "Configuring for Image processing with 4x H100 GPUs..."
        export OLLAMA_MODELS=/N/project/fads_ng/ollama_setup/ollama_models
        export OLLAMA_MAX_LOADED_MODELS=4
        
        # One instance per GPU for efficient parallel processing
        # GPU 0
        export CUDA_VISIBLE_DEVICES=0
        export OLLAMA_HOST="127.0.0.1:11434"
        ollama serve &
        
        # GPU 1
        export CUDA_VISIBLE_DEVICES=1
        export OLLAMA_HOST="127.0.0.1:11435"
        ollama serve &
        
        # GPU 2
        export CUDA_VISIBLE_DEVICES=2
        export OLLAMA_HOST="127.0.0.1:11436"
        ollama serve &
        
        # GPU 3
        export CUDA_VISIBLE_DEVICES=3
        export OLLAMA_HOST="127.0.0.1:11437"
        ollama serve &
        ;;
esac

# Install Ollama
pip install ollama
pip install tiktoken

# Pull models based on GPU type
if [ "$GPU_TYPE" = "image" ]; then
    echo "Pulling gemma3:27b model for image processing..."
    ollama pull gemma3:27b
else
    ollama pull qwen2.5:7b
fi

echo "Setup complete for $GPU_TYPE"
