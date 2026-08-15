# Two Sum

**Question ID:** `1`  
**Difficulty:** Easy  
**Category:** Array  
**Tags:** Array, Hash Table  
**Language:** C++  
**Submitted:** 1786818004

## Problem

You are given an array of integers
`nums`
and an integer
`target`
, return
*indices of the two numbers such that they add up to `target`*
.

You may assume that each input would have
**exactly one solution**
, and you may not use the
*same*
element twice.

You can return the answer in any order.

**Example 1:**

```
Input:
nums = [2,7,11,15], target = 9

Output:
[0,1]

Explanation:
Because nums[0] + nums[1] == 9, we return [0, 1].
```

**Example 2:**

```
Input:
nums = [3,2,4], target = 6

Output:
[1,2]
```

**Example 3:**

```
Input:
nums = [3,3], target = 6

Output:
[0,1]
```

**Constraints:**

- `2 <= nums.length <= 10 4`

- `-10 9 <= nums[i] <= 10 9`

- `-10 9 <= target <= 10 9`

- **Only one valid answer exists.**

**Follow-up:**
Can you come up with an algorithm that is less than
`O(n 2 )`

time complexity?

## Solution

```cpp
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
```
