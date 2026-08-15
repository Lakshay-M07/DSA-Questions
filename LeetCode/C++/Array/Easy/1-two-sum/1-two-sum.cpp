#include <vector>
#include <unordered_map>

class Solution {
public:
    std::vector<int> twoSum(std::vector<int>& nums, int target) {
        // Use an unordered_map to store values and their corresponding indices: {value: index}
        std::unordered_map<int, int> num_map;
        
        for (int i = 0; i < nums.size(); ++i) {
            int complement = target - nums[i];
            
            // Check if the required complement has already been seen
            if (num_map.find(complement) != num_map.end()) {
                // Return the index of the complement and the current index
                return {num_map[complement], i};
            }
            
            // Store the current value and its index in the map
            num_map[nums[i]] = i;
        }
        
        // Per constraints, a solution always exists, so this part is never reached
        return {};
    }
};
