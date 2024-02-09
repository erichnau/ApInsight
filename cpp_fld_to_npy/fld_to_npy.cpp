#define _CRT_SECURE_NO_WARNINGS

#include <iostream>
#include <fstream>
#include <vector>
#include <cstdint>
#include <cstring>
#include <cmath>
#include <chrono>
#include <cnpy.h>

void saveDataAsNpy(const std::vector<std::vector<std::vector<float>>>& data,
    const char* output_file_path) {

    int z_size = data.size();
    if (z_size == 0) {
        std::cerr << "Error: Empty data." << std::endl;
        return;
    }

    int y_size = data[0].size();
    if (y_size == 0) {
        std::cerr << "Error: Empty data." << std::endl;
        return;
    }

    int x_size = data[0][0].size();
    if (x_size == 0) {
        std::cerr << "Error: Empty data." << std::endl;
        return;
    }

    // Flatten the data for cnpy
    std::vector<float> flattened_data;
    flattened_data.reserve(x_size * y_size * z_size);

    for (int layer_index = 0; layer_index < z_size; ++layer_index) {
        for (int i = 0; i < y_size; ++i) {
            for (int j = 0; j < x_size; ++j) {
                flattened_data.push_back(data[layer_index][i][j]);
            }
        }
    }

    // Convert dimensions to unsigned long long for cnpy
    unsigned long long ull_x_size = static_cast<unsigned long long>(x_size);
    unsigned long long ull_y_size = static_cast<unsigned long long>(y_size);
    unsigned long long ull_z_size = static_cast<unsigned long long>(z_size);

    // Save the flattened data as npy
    cnpy::npy_save(output_file_path, &flattened_data[0], { ull_z_size, ull_y_size, ull_x_size }, "w");
}


// Function to read and interpret a double as big-endian
double readBigEndianDouble(std::ifstream& file) {
    double value;
    char rawValue[8];
    file.read(rawValue, 8);
    for (int i = 0; i < 8; ++i) {
        reinterpret_cast<char*>(&value)[7 - i] = rawValue[i];
    }
    return value;
}


// Function to read and interpret a 4-byte integer as big-endian
int32_t readBigEndianInt32(std::ifstream & file) {
    int32_t value;
    char rawValue[4];
    file.read(rawValue, 4);
    for (int i = 0; i < 4; ++i) {
        reinterpret_cast<char*>(&value)[3 - i] = rawValue[i];
    }
    return value;
}

// Function to read and interpret a float as big-endian
float readBigEndianFloat(std::ifstream& file) {
    float value;
    char rawValue[4];
    file.read(rawValue, 4);
    for (int i = 0; i < 4; ++i) {
        reinterpret_cast<char*>(&value)[3 - i] = rawValue[i];
    }
    return value;
}

int16_t readBigEndianInt16(std::ifstream& file) {
    int16_t value;
    char rawValue[2];
    file.read(rawValue, 2);
    reinterpret_cast<char*>(&value)[0] = rawValue[1];
    reinterpret_cast<char*>(&value)[1] = rawValue[0];
    return value;
}

// Function to read the FLD header
void readFldHeader(std::ifstream& file, int& version, int& xpixels, int& ypixels, int& zpixels,
    double& pixelsize, double& x_coor, double& y_coor, double& pixelsize_z, int& x_start, int& x_end, int& z_start, int& z_end) {

    char rawBytes[4];
    file.read(rawBytes, 4);

    // Interpret the raw bytes as a big-endian integer
    version = (static_cast<unsigned char>(rawBytes[0]) << 24) |
        (static_cast<unsigned char>(rawBytes[1]) << 16) |
        (static_cast<unsigned char>(rawBytes[2]) << 8) |
        static_cast<unsigned char>(rawBytes[3]);

    // Read xpixels, ypixels, and zpixels as big-endian integers
    xpixels = readBigEndianInt32(file);
    ypixels = readBigEndianInt32(file);
    zpixels = readBigEndianInt32(file);

    x_start = readBigEndianInt32(file);
    x_end = readBigEndianInt32(file);

    pixelsize = static_cast<double>(x_end - x_start) / static_cast<double>(xpixels) / 100.0;

    // Skip unused integers
    file.seekg(8, std::ios::cur);

    z_start = readBigEndianInt32(file);
    z_end = readBigEndianInt32(file);

    pixelsize_z = static_cast<double>(z_end - z_start) / static_cast<double>(zpixels) / 100.0;


    // Skip unused bytes
    file.seekg(158, std::ios::cur);

    // Read x_coor and y_coor as big-endian doubles
    x_coor = readBigEndianDouble(file);
    y_coor = readBigEndianDouble(file);
}


// Function to read the FLD data specs and return data_start
int readFldDataSpecs(std::ifstream& file, int z_size) {
    int start_b = 246;
    int stop_b = start_b + z_size * 4;

    file.seekg(stop_b + 4); // Skip 4 bytes

    int num_dt;
    num_dt = readBigEndianInt32(file);

    int start_b2 = stop_b + 8;
    int stop_b2 = start_b2 + num_dt * 4 * 2;

    int start_velo;
    start_velo = stop_b2 + num_dt * 4 * 2;
    
    file.seekg(start_velo); // Skip the time_depth_table

    int num_velo;
    num_velo = readBigEndianInt32(file);

    int velo_start = stop_b2 + num_dt * 4 * 2 + 4;
    int velo_stop = velo_start + num_velo * 2 * 4;
    file.seekg(velo_stop + 4); // Skip 4 bytes (epsg)

    int data_start = velo_stop + 4;
    return data_start;
}

// Function to read the FLD data
void readFldData(std::ifstream& file, int x_size, int y_size, int number_of_layers, std::vector<std::vector<std::vector<float>>>& data) {
    int data_start = readFldDataSpecs(file, number_of_layers);

    for (int layer_index = 0; layer_index < number_of_layers; ++layer_index) {
        int64_t number_of_values_layer;
        file.seekg(data_start);
        file.read(reinterpret_cast<char*>(&number_of_values_layer), sizeof(int64_t));

        float min1, max1;
        min1 = readBigEndianFloat(file);
        max1 = readBigEndianFloat(file);

        int data_stop = data_start + 16 + number_of_values_layer * 2;

        std::vector<int16_t> data_values(number_of_values_layer);
        file.seekg(data_start + 16);
        for (int i = 0; i < number_of_values_layer; ++i) {
            data_values[i] = readBigEndianInt16(file);
        }

        float packing_factor = (max1 - min1) / 32760;

        std::vector<float> data_unpacked(x_size * y_size, 0.0f); // Preallocate the vector

        int dataIndex = 0; // Initialize dataIndex

        for (int i = 0; i < number_of_values_layer; ++i) {
            int element = data_values[i];

            if (element > 0) {
                float value = min1 + (element - 1) * packing_factor;
                data_unpacked[dataIndex++] = value;
            }
            else {
                // Replace negative values with zeros at the same position
                int absElement = abs(element);
                for (int j = 0; j < absElement; ++j) {
                    data_unpacked[dataIndex++] = 0.0f;
                }
            }
        }

        for (int i = 0; i < y_size; ++i) {
            for (int j = 0; j < x_size; ++j) {
                data[layer_index][i][j] = data_unpacked[i * x_size + j];
            }
        }

        data_start = data_stop;
    }
}


int main(int argc, char* argv[]) {
    if (argc < 3) {
        std::cerr << "Please provide both input and output file paths." << std::endl;
        return 1;
    }

    const char* input_file_path = argv[1];
    const char* output_file_path = argv[2];

    std::ifstream file(input_file_path, std::ios::binary);

    if (!file) {
        std::cerr << "Unable to open file '" << input_file_path << "'." << std::endl;
        return 1;
    }

    int version, xpixels, ypixels, zpixels, x_start, x_end, z_start, z_end;
    double pixelsize, x_coor, y_coor, pixelsize_z;

    readFldHeader(file, version, xpixels, ypixels, zpixels, pixelsize, x_coor, y_coor, pixelsize_z, x_start, x_end, z_start, z_end);

    // Declare and initialize the 'data' vector
    std::vector<std::vector<std::vector<float>>> data(zpixels, std::vector<std::vector<float>>(ypixels, std::vector<float>(xpixels, 0.0f)));

    auto start_time = std::chrono::high_resolution_clock::now(); // Get the start time
    readFldData(file, xpixels, ypixels, zpixels, data); // Pass 'data' as an argument
    auto end_time = std::chrono::high_resolution_clock::now(); // Get the end time

    // Calculate the duration in seconds
    std::chrono::duration<double> elapsed_seconds = end_time - start_time;
    std::cout << "Time taken by readFldData: " << elapsed_seconds.count() << " seconds" << std::endl;

    std::cout << "Data processing completed." << std::endl;

    for (auto& layer : data) {
        std::reverse(layer.begin(), layer.end());
    }

    saveDataAsNpy(data, output_file_path);

    return 0;
}




