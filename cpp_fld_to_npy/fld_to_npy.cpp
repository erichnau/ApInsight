#define _CRT_SECURE_NO_WARNINGS

#include <iostream>
#include <fstream>
#include <vector>
#include <cstdint>
#include <cstring>
#include <cmath>
#include <chrono>
#include <cnpy.h>
#include <thread>
#include <future>
#include <mutex>

struct LayerInfo {
    int64_t data_start;
    int64_t number_of_values_layer;
    float min_value;
    float max_value;
};

void saveDataAsNpy(const std::vector<float>& flattened_data, const std::vector<uint64_t>& shape, const char* output_file_path) {
    if (flattened_data.empty()) {
        std::cerr << "Error: Empty data." << std::endl;
        return;
    }

    // Print the dimensions of the array
    std::cout << "Saving NPY file with dimensions: ";
    for (const auto& dim : shape) {
        std::cout << dim << " ";
    }
    std::cout << std::endl;

    // Save the flattened data as npy
    std::cout << "Saving data as NPY..." << std::endl;
    cnpy::npy_save(output_file_path, flattened_data.data(), shape, "w");
    std::cout << "Data saved as NPY." << std::endl;
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
int32_t readBigEndianInt32(std::ifstream& file) {
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

void preprocessLayerData(std::ifstream& file, int number_of_layers, std::vector<LayerInfo>& layer_infos) {
    int64_t data_start = readFldDataSpecs(file, number_of_layers);

    for (int layer_index = 0; layer_index < number_of_layers; ++layer_index) {
        int64_t number_of_values_layer;
        file.seekg(data_start);
        file.read(reinterpret_cast<char*>(&number_of_values_layer), sizeof(int64_t));

        float min1 = readBigEndianFloat(file);
        float max1 = readBigEndianFloat(file);

        int64_t data_stop = data_start + 16 + number_of_values_layer * 2;

        layer_infos.push_back({ data_start, number_of_values_layer, min1, max1 });

        data_start = data_stop;
    }
}

void processLayer(const std::string& input_file_path, int x_size, int y_size, int layer_index, const LayerInfo& layer_info, std::vector<float>& flattened_data, std::mutex& data_mutex) {
    std::ifstream file(input_file_path, std::ios::binary);
    if (!file) {
        std::cerr << "Unable to open file '" << input_file_path << "' for layer " << layer_index << std::endl;
        return;
    }

    int64_t data_start = layer_info.data_start;

    file.seekg(data_start + 16); // Skip the initial part of the layer

    if (file.fail()) {
        std::cerr << "Error seeking to data start for layer " << layer_index << std::endl;
        return;
    }

    std::vector<int16_t> data_values(layer_info.number_of_values_layer);
    for (int i = 0; i < layer_info.number_of_values_layer; ++i) {
        data_values[i] = readBigEndianInt16(file);
    }

    if (file.fail()) {
        std::cerr << "Error reading data values for layer " << layer_index << std::endl;
        return;
    }

    float packing_factor = (layer_info.max_value - layer_info.min_value) / 32760;

    std::vector<float> data_unpacked(x_size * y_size, 0.0f); // Preallocate the vector

    int dataIndex = 0; // Initialize dataIndex

    for (int i = 0; i < layer_info.number_of_values_layer; ++i) {
        int element = data_values[i];

        if (element > 0) {
            float value = layer_info.min_value + (element - 1) * packing_factor;
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

    // Reverse the data_unpacked along the y-axis (up-down)
    for (int i = 0; i < y_size / 2; ++i) {
        for (int j = 0; j < x_size; ++j) {
            std::swap(data_unpacked[i * x_size + j], data_unpacked[(y_size - i - 1) * x_size + j]);
        }
    }

    // Lock the mutex before modifying the shared flattened_data vector
    std::lock_guard<std::mutex> guard(data_mutex);

    // Calculate the offset for this layer in the flattened data vector
    size_t offset = static_cast<size_t>(layer_index) * x_size * y_size;

    // Flatten the layer data and store it in the correct position within the flattened_data vector
    for (int i = 0; i < y_size; ++i) {
        for (int j = 0; j < x_size; ++j) {
            flattened_data[offset + i * x_size + j] = data_unpacked[i * x_size + j];
        }
    }
}

void readFldData(const std::string& input_file_path, int x_size, int y_size, int number_of_layers, const std::vector<LayerInfo>& layer_infos, std::vector<float>& flattened_data) {
    std::vector<std::future<void>> futures;
    std::mutex data_mutex;

    for (int layer_index = 0; layer_index < number_of_layers; ++layer_index) {
        const LayerInfo& layer_info = layer_infos[layer_index];

        futures.push_back(std::async(std::launch::async, processLayer, input_file_path, x_size, y_size, layer_index, layer_info, std::ref(flattened_data), std::ref(data_mutex)));
    }

    for (auto& future : futures) {
        future.get();
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

    auto total_start_time = std::chrono::high_resolution_clock::now();

    auto start_time = total_start_time;
    std::cout << "Reading FLD header..." << std::endl;
    readFldHeader(file, version, xpixels, ypixels, zpixels, pixelsize, x_coor, y_coor, pixelsize_z, x_start, x_end, z_start, z_end);
    std::cout << "FLD header read." << std::endl;

    auto end_time = std::chrono::high_resolution_clock::now();
    std::chrono::duration<double> elapsed_seconds = end_time - start_time;
    std::cout << "Time taken to read FLD header: " << elapsed_seconds.count() << " seconds" << std::endl;

    std::vector<LayerInfo> layer_infos;

    start_time = std::chrono::high_resolution_clock::now();
    std::cout << "Preprocessing layer data..." << std::endl;
    preprocessLayerData(file, zpixels, layer_infos);
    std::cout << "Layer data preprocessed." << std::endl;

    end_time = std::chrono::high_resolution_clock::now();
    elapsed_seconds = end_time - start_time;
    std::cout << "Time taken to preprocess layer data: " << elapsed_seconds.count() << " seconds" << std::endl;

    // Prepare the flattened data vector and shape vector
    std::vector<float> flattened_data(static_cast<size_t>(xpixels) * ypixels * zpixels, 0.0f);
    std::vector<uint64_t> shape{ static_cast<uint64_t>(zpixels), static_cast<uint64_t>(ypixels), static_cast<uint64_t>(xpixels) };

    start_time = std::chrono::high_resolution_clock::now(); // Get the processing start time
    std::cout << "Reading FLD data..." << std::endl;
    readFldData(input_file_path, xpixels, ypixels, zpixels, layer_infos, flattened_data); // Pass 'layer_infos' and 'flattened_data' as arguments

    end_time = std::chrono::high_resolution_clock::now();
    elapsed_seconds = end_time - start_time;
    std::cout << "Time taken to read and process FLD data: " << elapsed_seconds.count() << " seconds" << std::endl;

    std::cout << "Data processing completed." << std::endl;

    start_time = std::chrono::high_resolution_clock::now(); // Get the saving start time
    saveDataAsNpy(flattened_data, shape, output_file_path);
    end_time = std::chrono::high_resolution_clock::now();
    elapsed_seconds = end_time - start_time;
    std::cout << "Time taken to save NPY file: " << elapsed_seconds.count() << " seconds" << std::endl;

    auto total_end_time = std::chrono::high_resolution_clock::now();
    auto total_elapsed_seconds = std::chrono::duration_cast<std::chrono::seconds>(total_end_time - total_start_time).count();
    std::cout << "Total process time: " << total_elapsed_seconds << " seconds" << std::endl;
    std::cout << "Process completed successfully. Exiting C++ Executable" << std::endl;

    file.close(); // Ensure the file is properly closed

    std::exit(0); // Explicitly exit the program
    return 0;
}
