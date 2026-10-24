# FireWatch · 火焰图像分析工作台

可解释的视觉分析应用。通过 OpenCV 提取颜色、亮度和边缘特征，在网页中调节参数、查看候选区域，并保存可追溯的分析记录。

## 功能

- JPEG／PNG／WebP 上传，检查解码结果、10 MB 上限与 1200 万像素上限。
- Sobel、Canny、Laplacian、Scharr 四种边缘算子；颜色和亮度联合规则、形态学闭运算与连通域过滤。
- 原图、候选掩膜与区域叠加图；各算子的邻域命中率、判定与算法耗时。
- FastAPI 检测接口、SQLite 历史、结果图片和 JSON 报告下载。
- 独立标注清单评估入口，输出图像级混淆矩阵、Precision／Recall／F1。

## 启动

Python 3.9+，在本目录运行：

```sh
python3 -m venv .venv
.venv/bin/python -m pip install -r requirements.txt
.venv/bin/python -m uvicorn app.main:app --host 127.0.0.1 --port 8765
```

浏览器打开 http://127.0.0.1:8765 ，API 文档在 `/docs`。本机已准备 `.venv`，也可双击上一级 `启动火灾检测.command`。本地结果在 `data/`，可用 `FIREWATCH_DATA` 指定其他目录。服务为单人本机演示。

## 算法与解释

Sobel／Scharr 使用 X、Y 浮点梯度幅值；Laplacian 保留有符号梯度再取绝对值。亮度阈值与 `R > mean(R), R > G, G < 200, B < 100` 共同构成颜色候选区。闭运算连接局部区域，连通域面积过滤去除小噪点。

边缘邻域命中率 = 具有 1 像素颜色／亮度支持的边缘像素数 / 边缘像素数。区域占比 = 候选掩膜像素数 / 整幅图像像素数。每种算子结合邻域命中率、最小区域占比和连通域判定；总体结果为任一算子触发。这两个比例不是置信度或准确率。

界面直接展示最终应用，不要求使用者阅读课程作业对照。历史 C++ 资料位于 `original/`，不参与运行。

## 验证与实验

```sh
.venv/bin/python -m unittest discover -s tests -v
.venv/bin/python scripts/evaluate.py test_manifest.csv --output evaluation.json
```

清单表头为 `path,label`，label 为 0／1，图像路径相对于 CSV。测试集应按图像或视频来源独立划分，包含夕阳、灯光、橙色物体等难负样本。阈值调整使用验证集。脚本计算图像级指标，不计算分割 IoU。

18 项单元／接口测试已通过，覆盖边缘极性、区域过滤、异常上传、完整记录链路和报告校验。`tests/synthetic_candidate.png` 仅用于演示规则，不是真实火焰照片。本次未获得独立真实标注集，因此未宣称准确率、实时报警或生产部署能力。

## 可复核的图像处理记录

每次新分析都会保存输入字节 SHA-256、检测器代码 SHA-256、算法名称、参数、OpenCV／NumPy／Python 版本及七张输出 PNG 的哈希。分析指纹由输入、检测器、参数与关键依赖版本共同生成；同一输入和参数重复分析的指纹一致，参数改变会改变指纹。

记录文件夹同时保存 `report.json`。校验命令：

```sh
.venv/bin/python scripts/verify_run.py data/你的记录编号
```

校验检查输出缺失／改变、清单完整性、参数一致性和指纹，不是数字签名或防伪机制，也不能证明检测准确率。旧记录没有新增字段，仍可在网页读取，但不能通过新校验入口验证。

容器配置及验证边界见 [部署说明](../DEPLOYMENT.md)。

技术参考：[OpenCV 梯度](https://docs.opencv.org/4.13.0/d5/d0f/tutorial_py_gradients.html)、[FastAPI 上传](https://fastapi.tiangolo.com/tutorial/request-files/)。项目作品版：2026-10。
