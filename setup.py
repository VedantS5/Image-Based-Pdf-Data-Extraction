from setuptools import setup, find_packages

# Read the long description from README.md
try:
    with open("README.md", "r", encoding="utf-8") as fh:
        long_description = fh.read()
except:
    long_description = "Extract author metadata from PDF analyst reports using multimodal LLMs and image processing."

setup(
    name="analyst-report-vision",
    version="0.1.0",
    description="A specialized tool for extracting author information from financial analyst reports using multimodal LLMs with image processing capabilities",
    long_description=long_description,
    long_description_content_type="text/markdown",
    author="FADS Team",
    author_email="vedantshah@iu.edu",
    packages=find_packages(),
    py_modules=["02_image"],
    install_requires=[
        "pymupdf>=1.22.0",
        "requests>=2.28.0",
        "pandas>=1.5.0",
        "numpy>=1.23.0",
        "ollama>=0.1.0",
        "tiktoken>=0.5.0",
        "pillow>=9.0.0",
        "tqdm>=4.64.0",
    ],
    entry_points={
        'console_scripts': [
            'analyst-report-vision=02_image:main',
        ],
    },
    classifiers=[
        "Programming Language :: Python :: 3",
        "License :: OSI Approved :: MIT License",
        "Operating System :: OS Independent",
        "Development Status :: 4 - Beta",
        "Intended Audience :: Financial and Insurance Industry",
        "Intended Audience :: Science/Research",
        "Topic :: Scientific/Engineering :: Artificial Intelligence",
        "Topic :: Office/Business :: Financial",
    ],
    python_requires=">=3.8",
    project_urls={
        "Source": "https://github.com/VedantS5/analyst-report-vision",
        "Issue Tracker": "https://github.com/VedantS5/analyst-report-vision/issues",
    }
)
