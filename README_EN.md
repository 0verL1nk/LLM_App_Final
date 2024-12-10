# Literature Reading Assistant
[简体中文](README.md) | English

An AI-powered literature reading assistant tool that helps researchers and students read, understand, and analyze academic literature more efficiently.

## ✨ Key Features

- 🔐 Complete User System (Login/Register)
- 📁 File Management Center
- 📑 Intelligent Literature Analysis
  - Automatic key text extraction and annotation
  - Literature summary generation
  - Smart text optimization and paraphrasing
  - Interactive paper Q&A
- 🗺️ Visual Mind Mapping
  - Based on st_pyecharts and pyecharts.charts.Tree
  - Intuitive display of literature structure and key concepts

## 🚀 Quick Start

### Requirements
- Python 3.8+
- pip < 24.1 (`python -m pip install pip==24.0`)

### Installation Steps

1. **Clone Repository**      
```bash
git clone <repository-url>
cd <project-directory>   
```

2. **Create Virtual Environment**      
```bash
python -m venv venv
# Linux/MacOS
source venv/bin/activate
# Windows
venv\Scripts\activate   
```

3. **Install Dependencies**      
```bash
pip install -r requirements.txt   
```

4. **Set Environment Variables**      
Remember to set the environment variable `DASHSCOPE_API_KEY`. Please refer to [First API Call to Qwen](https://help.aliyun.com/zh/model-studio/getting-started/first-api-call-to-qwen) documentation.
5. **Run Project**      
```bash
streamlit run file_center.py   
```

6. **Access Application**
Open browser and visit `http://localhost:8501`

## 📸 Feature Showcase

### Login Interface
![Login Interface](images/登录.png)

### File Center
![File Center](images/%E6%96%87%E4%BB%B6%E4%B8%AD%E5%BF%83.png)

### Text Extraction
![Text Extraction](images/%E5%8E%9F%E6%96%87%E6%8F%90%E5%8F%96.png)

### Text Optimization
![Text Optimization Example](images/文段优化1.png)
![Text Optimization Example](images/文段优化3.png)
![Text Optimization Result](images/文段优化4.png)

### Paper Q&A
![Paper Q&A](images/论文问答.png)
![Q&A Example](images/论文问答2.png)

### Mind Map
![Mind Map](images/思维导图.png)

## 🛠️ Tech Stack

- Frontend: Streamlit
- Backend: Python
- Visualization: pyecharts

## 🗺️ Roadmap

- [x] User System
- [x] File Center
- [x] Core Literature Analysis Features
- [x] Mind Map Visualization
- [x] LangChain Framework Integration
- [ ] Refactor: Migrate utils to separate folder
- [ ] ~~One-click Paper Translation~~ (Suspended)

## 📝 Notes

- pip version needs to be less than 24.1, you can install the specified version using:  ```bash
  python -m pip install pip==24.0  ```

## 🤝 Contributing

Issues and Pull Requests are welcome to help improve the project! 