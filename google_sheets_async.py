import asyncio
import re

import gspread_asyncio
from google.oauth2.service_account import Credentials


def get_creds():
    creds = Credentials.from_service_account_file("./service_account.json")
    scoped = creds.with_scopes([
        "https://www.googleapis.com/auth/spreadsheets",
        "https://www.googleapis.com/auth/drive",
    ])
    return scoped


agcm_royleague = gspread_asyncio.AsyncioGspreadClientManager(get_creds)


class PlayerNotFound(Exception):
    def __init__(self, player):
        self.player = player


async def update_league_sheet(agcm: gspread_asyncio.AsyncioGspreadClientManager,
                              result: dict[str, str, tuple[str, str], tuple[str, str]]) -> bool:
    agc = await agcm.authorize()
    # print(await agc.openall())
    sh = await agc.open("Royleague_S3_Tables_WIP")  # TODO make some command to assign other names if needed

    wks = await sh.worksheet(f"{result['league']} {result['division']}")

    score_projection = dict()

    p1_criteria = re.compile(fr'.? ?({result["player1"][0]})(#\d{4})?', flags=re.IGNORECASE)
    p1_found = await wks.findall(p1_criteria)
    if not p1_found:
        raise PlayerNotFound(result['player1'][0])
    score_projection[p1_found[0].value] = result['player1'][1]

    p2_criteria = re.compile(fr'.? ?({result["player2"][0]})(#\d{4})?', flags=re.IGNORECASE)
    p2_found = await wks.findall(p2_criteria)
    if not p2_found:
        raise PlayerNotFound(result['player2'][0])
    score_projection[p2_found[0].value] = result['player2'][1]

    for p1, p2 in zip(p1_found, p2_found):
        if (p1_row := p1.row) == p2.row:
            p1, p2 = sorted((p1, p2), key=lambda c: gspread_asyncio.a1_to_rowcol(c.address))
            # print(p1, p2)
            p1_score = await wks.cell(p1_row, p1.col+2)
            p2_score = await wks.cell(p1_row, p2.col+3)
            # print(p1_score.value, type(p1_score.value), p1_score.address)
            # print(p2_score.value, type(p2_score.value), p2_score.address)
            if not p1_score.value or not p2_score.value:
                await wks.update(f"{p1_score.address}:{p2_score.address}",
                                 [[score_projection[p1.value], ':', score_projection[p2.value]]])
                return True
    return False


async def list_players(agcm: gspread_asyncio.AsyncioGspreadClientManager,
                       league: str, division: str) -> list[list[str]]:
    agc = await agcm.authorize()
    sh = await agc.open("Royleague_S3_Tables_WIP")  # TODO same stuff there
    wks = await sh.worksheet(f"{league} {division}")

    standings = await wks.get_values('H4:P13', major_dimension='ROWS')
    return standings


if __name__ == "__main__":
    resultTest = {'league': 'EU', 'division': 'CL', 'player1': ('Baffest', 2), 'player2': ('FaYaY', 6)}
    # asyncio.run(update_league_sheet(agcm_royleague, result=resultTest), debug=True)
    asyncio.run(list_players(agcm_royleague, 'EU', 'CL'))
