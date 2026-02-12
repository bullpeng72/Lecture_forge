from setuptools import setup, find_packages

with open("README.md", "r", encoding="utf-8") as fh:
    long_description = fh.read()

with open("requirements.txt", "r", encoding="utf-8") as fh:
    requirements = [line.strip() for line in fh if line.strip() and not line.startswith("#")]

setup(
    name="lecture-forge",
    version="0.3.0",
    author="Sungwoo Kim",
    author_email="sungwoo.kim@gmail.com",
    description="AI-powered lecture material generator using LangChain",
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
            ".env.example",
        ],
    },
)
