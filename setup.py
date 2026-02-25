from setuptools import setup, find_packages

with open("README.md", "r", encoding="utf-8") as fh:
    long_description = fh.read()

with open("requirements.txt", "r", encoding="utf-8") as fh:
    requirements = []
    for line in fh:
        line = line.strip()
        # Skip empty lines and comments
        if not line or line.startswith("#"):
            continue
        # Handle conditional requirements (e.g., numpy with python_version conditions)
        if ";" in line:
            # Keep the full conditional requirement
            requirements.append(line)
        else:
            requirements.append(line)

setup(
    name="lecture-forge",
    version="0.4.3",
    author="Sungwoo Kim",
    author_email="sungwoo.kim@gmail.com",
    description="AI-powered lecture material generator with multilingual support using LangChain",
    long_description=long_description,
    long_description_content_type="text/markdown",
    url="https://github.com/bullpeng72/Lecture_forge",
    packages=find_packages(where="src"),
    package_dir={"": "src"},
    classifiers=[
        "Development Status :: 4 - Beta",
        "Intended Audience :: Education",
        "Topic :: Education",
        "License :: OSI Approved :: MIT License",
        "Programming Language :: Python :: 3",
        "Programming Language :: Python :: 3.11",
        "Programming Language :: Python :: 3.12",
        "Programming Language :: Python :: 3.13",
    ],
    python_requires=">=3.11",
    install_requires=requirements,
    entry_points={
        "console_scripts": [
            "lecture-forge=lecture_forge.cli:cli",
        ],
    },
    include_package_data=True,
    package_data={
        "lecture_forge": [
            "templates/*.html",
            "templates/*.css",
            "templates/*.js",
            "templates/prompts/*.txt",
            ".env.example",
        ],
    },
)
