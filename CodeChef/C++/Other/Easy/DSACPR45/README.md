# coding skills with our Sum of Array elements

**Question ID:** `DSACPR45`  
**Difficulty:** Easy  
**Category:** Other  
**Tags:** Other  
**Language:** C++  
**Submitted:** 45 min ago

## Problem

Improve your coding skills with our Sum of Array elements practice problem! Challenge yourself and solve Sum of Array elements practical programming coding exercises.

## Solution

```cpp
#include <iostream>
using namespace std;
int main() {
    //Boosts the speed of cin and cout
    
    ios_base::sync_with_stdio(false);
    cin.tie(NULL);
    
    int n;
    cin >> n;
    
    long long sum = 0; //Using long long to prevent any potential overflow
    for(int i = 0; i < n; i++){
        int element;
        cin >> element;
        sum += element;
    }
    
    cout << sum << "\n";
    
    return 0;
}
```
