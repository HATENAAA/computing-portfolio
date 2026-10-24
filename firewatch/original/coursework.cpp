#include <opencv2/opencv.hpp>
#include <iostream>
using namespace cv;
using namespace std;
// 计算符合火焰特征的像素占边缘图像的比例
double calculateFireAreaRatio(const Mat& edges, const Mat& img, const Mat& binary_img, double Rmean) {
    int firePixels = 0;
    int edgePixels = 0;
    // 遍历边缘图像，计算符合火焰特征的像素占比
    for (int y = 0; y < edges.rows; y++) {
        for (int x = 0; x < edges.cols; x++) {
            if (edges.at<uchar>(y, x) == 255) {  
                edgePixels++;
                Vec3b color = img.at<Vec3b>(y, x);
                int R = color[2];  
                int G = color[1]; 
                int B = color[0];  
                // 判断像素是否符合火焰特征
                if (R > Rmean && R > G && G < 200 && B < 100) {
                    firePixels++;
                }
            }
        }
    }
    // 返回符合火焰特征的像素比例
    return edgePixels > 0 ? (double)firePixels / edgePixels : 0;
}
// 边缘检测函数
void edgeDetection(const Mat& gray_img, Mat& edges, const string& method) {
    if (method == "Sobel") {
        Sobel(gray_img, edges, CV_8U, 1, 1, 3);  // Sobel边缘检测
    }
    else if (method == "Canny") {
        Canny(gray_img, edges, 100, 200);  // Canny边缘检测
    }
    else if (method == "Laplacian") {
        Laplacian(gray_img, edges, CV_8U, 3);  // 拉普拉斯边缘检测
    }
    else if (method == "Scharr") {
        Scharr(gray_img, edges, CV_8U, 1, 0);  // Scharr边缘检测
    }
}
// 基于颜色特征的火焰区域提取
Mat extractFireRegionByColor(const Mat& img, double Rmean) {
    Mat fire_region = Mat::zeros(img.size(), CV_8UC3);  
    for (int y = 0; y < img.rows; y++) {
        for (int x = 0; x < img.cols; x++) {
            Vec3b color = img.at<Vec3b>(y, x);
            int R = color[2]; 
            int G = color[1]; 
            int B = color[0];  
            if (R > Rmean && R > G && G < 200 && B < 100) {
                fire_region.at<Vec3b>(y, x) = img.at<Vec3b>(y, x);  
            }
        }
    }
    return fire_region;
}
// 进行闭运算以填补火焰区域的空洞
Mat applyClosing(const Mat& edges) {
    Mat closed_edges;
    Mat kernel = getStructuringElement(MORPH_RECT, Size(3, 3));
    morphologyEx(edges, closed_edges, MORPH_CLOSE, kernel);
    return closed_edges;
}
// 进行二值化处理，排除亮度较低的部分
Mat applyThresholding(const Mat& gray_img, double threshold_value) {
    Mat binary_img;
    threshold(gray_img, binary_img, threshold_value, 255, THRESH_BINARY);
    return binary_img;
}
int main() {
    Mat img1 = imread("flame1.jpg");
    Mat img2 = imread("flame2.jpg");
    if (img1.empty() || img2.empty()) {
        cout << "无法加载图像，请检查路径!" << endl;
        return -1;
    }
    Mat gray_img1, gray_img2;
    cvtColor(img1, gray_img1, COLOR_BGR2GRAY);  // 转换为灰度图像
    cvtColor(img2, gray_img2, COLOR_BGR2GRAY);  // 转换为灰度图像
    // 对灰度图像进行二值化处理
    double threshold_value = 150; 
    Mat binary_img1 = applyThresholding(gray_img1, threshold_value);
    Mat binary_img2 = applyThresholding(gray_img2, threshold_value);
    // 计算红色分量均值
    Scalar mean_color1 = mean(img1);
    Scalar mean_color2 = mean(img2);
    double Rmean1 = mean_color1[2];
    double Rmean2 = mean_color2[2];
    // 边缘检测
    Mat edges1_sobel, edges2_sobel;
    Mat edges1_canny, edges2_canny;
    Mat edges1_laplacian, edges2_laplacian;
    Mat edges1_scharr, edges2_scharr;
    edgeDetection(binary_img1, edges1_sobel, "Sobel");
    edgeDetection(binary_img2, edges2_sobel, "Sobel");
    edgeDetection(binary_img1, edges1_canny, "Canny");
    edgeDetection(binary_img2, edges2_canny, "Canny");
    edgeDetection(binary_img1, edges1_laplacian, "Laplacian");
    edgeDetection(binary_img2, edges2_laplacian, "Laplacian");
    edgeDetection(binary_img1, edges1_scharr, "Scharr");
    edgeDetection(binary_img2, edges2_scharr, "Scharr");
    // 对边缘图像进行闭运算
    Mat closed_edges1_sobel = applyClosing(edges1_sobel);
    Mat closed_edges2_sobel = applyClosing(edges2_sobel);
    Mat closed_edges1_canny = applyClosing(edges1_canny);
    Mat closed_edges2_canny = applyClosing(edges2_canny);
    Mat closed_edges1_laplacian = applyClosing(edges1_laplacian);
    Mat closed_edges2_laplacian = applyClosing(edges2_laplacian);
    Mat closed_edges1_scharr = applyClosing(edges1_scharr);
    Mat closed_edges2_scharr = applyClosing(edges2_scharr);
    // 基于颜色特征的火焰区域提取
    Mat fire_region1_color = extractFireRegionByColor(img1, Rmean1);
    Mat fire_region2_color = extractFireRegionByColor(img2, Rmean2);
    //计算火焰区域的占比
    double fireAreaRatio1_sobel = calculateFireAreaRatio(closed_edges1_sobel, img1, binary_img1, Rmean1);
    double fireAreaRatio2_sobel = calculateFireAreaRatio(closed_edges2_sobel, img2, binary_img2, Rmean2);
    double fireAreaRatio1_canny = calculateFireAreaRatio(closed_edges1_canny, img1, binary_img1, Rmean1);
    double fireAreaRatio2_canny = calculateFireAreaRatio(closed_edges2_canny, img2, binary_img2, Rmean2);
    double fireAreaRatio1_laplacian = calculateFireAreaRatio(closed_edges1_laplacian, img1, binary_img1, Rmean1);
    double fireAreaRatio2_laplacian = calculateFireAreaRatio(closed_edges2_laplacian, img2, binary_img2, Rmean2);
    double fireAreaRatio1_scharr = calculateFireAreaRatio(closed_edges1_scharr, img1, binary_img1, Rmean1);
    double fireAreaRatio2_scharr = calculateFireAreaRatio(closed_edges2_scharr, img2, binary_img2, Rmean2);
    // 判断是否符合60%以上火焰特征
    bool isFireDetected1_sobel = fireAreaRatio1_sobel >= 0.6;
    bool isFireDetected2_sobel = fireAreaRatio2_sobel >= 0.6;
    bool isFireDetected1_canny = fireAreaRatio1_canny >= 0.6;
    bool isFireDetected2_canny = fireAreaRatio2_canny >= 0.6;
    bool isFireDetected1_laplacian = fireAreaRatio1_laplacian >= 0.6;
    bool isFireDetected2_laplacian = fireAreaRatio2_laplacian >= 0.6;
    bool isFireDetected1_scharr = fireAreaRatio1_scharr >= 0.6;
    bool isFireDetected2_scharr = fireAreaRatio2_scharr >= 0.6;
    //输出检测结果
    cout << "Image 1 - Sobel: Fire Area Ratio = " << fireAreaRatio1_sobel * 100 << "%, "
        << (isFireDetected1_sobel ? "Fire Detected" : "No Fire") << endl;
    cout << "Image 2 - Sobel: Fire Area Ratio = " << fireAreaRatio2_sobel * 100 << "%, "
        << (isFireDetected2_sobel ? "Fire Detected" : "No Fire") << endl;
    cout << "Image 1 - Canny: Fire Area Ratio = " << fireAreaRatio1_canny * 100 << "%, "
        << (isFireDetected1_canny ? "Fire Detected" : "No Fire") << endl;
    cout << "Image 2 - Canny: Fire Area Ratio = " << fireAreaRatio2_canny * 100 << "%, "
        << (isFireDetected2_canny ? "Fire Detected" : "No Fire") << endl;
    cout << "Image 1 - Laplacian: Fire Area Ratio = " << fireAreaRatio1_laplacian * 100 << "%, "
        << (isFireDetected1_laplacian ? "Fire Detected" : "No Fire") << endl;
    cout << "Image 2 - Laplacian: Fire Area Ratio = " << fireAreaRatio2_laplacian * 100 << "%, "
        << (isFireDetected2_laplacian ? "Fire Detected" : "No Fire") << endl;
    cout << "Image 1 - Scharr: Fire Area Ratio = " << fireAreaRatio1_scharr * 100 << "%, "
        << (isFireDetected1_scharr ? "Fire Detected" : "No Fire") << endl;
    cout << "Image 2 - Scharr: Fire Area Ratio = " << fireAreaRatio2_scharr * 100 << "%, "
        << (isFireDetected2_scharr ? "Fire Detected" : "No Fire") << endl;
    //显示结果
    imshow("Fire Region - Sobel 1 - Closed", closed_edges1_sobel);
    imshow("Fire Region - Sobel 2 - Closed", closed_edges2_sobel);
    imshow("Fire Region - Canny 1 - Closed", closed_edges1_canny);
    imshow("Fire Region - Canny 2 - Closed", closed_edges2_canny);
    imshow("Fire Region - Laplacian 1 - Closed", closed_edges1_laplacian);
    imshow("Fire Region - Laplacian 2 - Closed", closed_edges2_laplacian);
    imshow("Fire Region - Scharr 1 - Closed", closed_edges1_scharr);
    imshow("Fire Region - Scharr 2 - Closed", closed_edges2_scharr);
    // 显示基于颜色特征的火焰区域提取结果
    imshow("Fire Region - Color Method 1", fire_region1_color);
    imshow("Fire Region - Color Method 2", fire_region2_color);
    waitKey(0);
    return 0;
}