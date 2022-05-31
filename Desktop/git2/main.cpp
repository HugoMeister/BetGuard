#include <iostream>
#include <math.h>
#include "headers.h"
using namespace std;
int main()
{
    extern int p1, p2;
    extern char first, second;
    extern char board;
    cout << "Player 1 choose X or Y" << endl;
    cin >> first;
    cout << "Player 2 choose X or Y" << endl;
    cin >> second;
    system("clear");
    drawBoard();
    int counter = 0;
    while (true)
    {
        cout << "Player 1 (" << first << ") your turn" << endl;
        cin >> p1;
        playersMove();
        system("clear");
        drawBoard();
        if (checkWinner() == 'X')
        {
            cout << "Winner is X" << endl;
            break;
        }
        else if (checkWinner() == 'Y')
        {
            cout << "Winner is Y" << endl;
            break;
        }
        else if (checkWinner() == '/')
        {
            ++counter;
            if (counter == 9)
            {
                cout << "It's draw game" << endl;
            }
        }
        cout << "Player 2 (" << second << ") your turn" << endl;
        cin >> p2;
        playersMove();
        system("clear");
        drawBoard();
        if (checkWinner() == 'X')
        {
            cout << "Winner is X" << endl;
            break;
        }
        else if (checkWinner() == 'Y')
        {
            cout << "Winner is Y" << endl;
            break;
        }
        else if (checkWinner() == '/')
        {
            ++counter;
            if (counter == 9)
            {
                cout << "It's draw game" << endl;
            }
        }
    }
}
