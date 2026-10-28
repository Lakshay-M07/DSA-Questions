#include <stdio.h>
#include <stdlib.h>
struct node{
    int val;
    struct node* left;
    struct node* right;
};
struct node* node_new(int val){
    struct node* temp = (struct node*)malloc(sizeof(struct node));
    temp->val = val;
    temp->left = NULL;
    temp->right = NULL;
    return temp;
}
int main() {
    // Creating our root node
    struct node* root = node_new(0);
    // Assigning node '1' to the left of '0'
    root->left = node_new(1);
    // Assigning node '2' to the right of '0'
    root->right = node_new(2);
    // Similarly for the child nodes of the left(1)
    root->left->left = node_new(3);
    root->left->right = node_new(4);
    printf("The tree is created!\n");
    return 0;
}
