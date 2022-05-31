#include <iostream>
#include <math.h>
using namespace std;
#include "headers.h";
int p1, p2;
char first, second;
char board[9] = {'1', '2', '3', '4', '5', '6', '7', '8', '9'};
void drawBoard()
{
    cout << "---------" << endl;
    cout << board[0] << " | " << board[1] << " | " << board[2] << endl;
    cout << "---------" << endl;
    cout << board[3] << " | " << board[4] << " | " << board[5] << endl;
    cout << "---------" << endl;
    cout << board[6] << " | " << board[7] << " | " << board[8] << endl;
    cout << "---------" << endl;
}
void playersMove()
{
    if (p1 == 1)
    {
        board[0] = first;
    }
    else if (p2 == 1)
    {
        board[0] = second;
    }
    if (p1 == 2)
    {
        board[1] = first;
    }
    else if (p2 == 2)
    {
        board[1] = second;
    }
    if (p1 == 3)
    {
        board[2] = first;
    }
    else if (p2 == 3)
    {
        board[2] = second;
    }
    if (p1 == 4)
    {
        board[3] = first;
    }
    else if (p2 == 4)
    {
        board[3] = second;
    }
    if (p1 == 5)
    {
        board[4] = first;
    }
    else if (p2 == 5)
    {
        board[4] = second;
    }
    if (p1 == 6)
    {
        board[5] = first;
    }
    else if (p2 == 6)
    {
        board[5] = second;
    }
    if (p1 == 7)
    {
        board[6] = first;
    }
    else if (p2 == 7)
    {
        board[6] = second;
    }
    if (p1 == 8)
    {
        board[7] = first;
    }
    else if (p2 == 8)
    {
        board[7] = second;
    }
    if (p1 == 9)
    {
        board[8] = first;
    }
    else if (p2 == 9)
    {
        board[8] = second;
    }
}
char checkWinner()
{
    if (board[0] == first && board[1] == first && board[2] == first)
    {
        return 'X';
    }

    if (board[3] == first && board[4] == first && board[5] == first)
    {
        return 'X';
    }
    if (board[6] == first && board[7] == first && board[8] == first)
    {
        return 'X';
    }
    if (board[0] == first && board[3] == first && board[6] == first)
    {
        return 'X';
    }
    if (board[1] == first && board[4] == first && board[7] == first)
    {
        return 'X';
    }
    if (board[2] == first && board[5] == first && board[8] == first)
    {
        return 'X';
    }
    if (board[0] == first && board[4] == first && board[8] == first)
    {
        return 'X';
    }
    if (board[2] == first && board[4] == first && board[6] == first)
    {
        return 'X';
    }

    if (board[0] == second && board[1] == second && board[2] == second)
    {
        return 'Y';
    }
    if (board[3] == second && board[4] == second && board[5] == second)
    {
        return 'Y';
    }
    if (board[6] == second && board[7] == second && board[8] == second)
    {
        return 'Y';
    }
    if (board[0] == second && board[3] == second && board[6] == second)
    {
        return 'Y';
    }
    if (board[1] == second && board[4] == second && board[7] == second)
    {
        return 'Y';
    }
    if (board[2] == second && board[5] == second && board[8] == second)
    {
        return 'Y';
    }
    if (board[0] == second && board[4] == second && board[8] == second)
    {
        return 'Y';
    }
    if (board[2] == second && board[4] == second && board[6] == second)
    {
        return 'Y';
    }
    return '/';
}