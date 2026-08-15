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
