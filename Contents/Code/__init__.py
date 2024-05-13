import json
import urllib2
import re
import os
import ConfigParser


def Start():
    Log("Plugin gestartet.")


beatSaverBaseUrl = 'https://api.beatsaver.com/maps/id/{}'
scoreSaberPlayerScoresUrl = 'https://scoresaber.com/api/player/{}/scores?limit=10&sort=recent&page={}&withMetadata=true'


class PersonalShowsAgent(Agent.Movies):
    name = 'Beat Saber'
    languages = [Locale.Language.NoLanguage]
    primary_provider = True
    persist_stored_files = False

    def search(self, results, media, lang):
        Log.Info('Searching Metadata')
        x = "My Title %s" % (media.name)
        for item in media.items:
            for part in item.parts:
                file_path = part.file
                filename = os.path.basename(file_path)
                id = getIdFromFilename(filename)
                score = getScoreFromFilename(filename)
                map = Map(id)
                results.Append(
                    MetadataSearchResult(id="{}_{}".format(map.mapName, score), score=score, name=map.mapName,
                                         lang=Locale.Language.NoLanguage))

    def update_poster(self, metadata, link, base_path=None):
        Log.Info('Updating Poster')

    def update(self, metadata, media, lang):
        Log.Info('Updating Metadata')
        Log.Info(dir(metadata))
        for item in media.items:
            for part in item.parts:
                file_path = part.file
                filename = os.path.basename(file_path)
                id = getIdFromFilename(filename)
                score = getScoreFromFilename(filename)
                mapScore = None
                try:
                    hash = getMapHash(id)
                    mapScore = ScoreSaberScore(hash, score)
                    metadata.summary = "{}\n{}".format("https://beatsaver.com/maps/{}".format(map.id), mapScore)
                    metadata.content_rating = str(mapScore.rating)
                    metadata.rating = float(mapScore.accuracy) * 10
                    metadata.rating_image = 'https://uxwing.com/wp-content/themes/uxwing/download/seo-marketing/accurate-icon.png'
                except Exception as e:
                    Log.Info(e.message)
                map = Map(id, score.diff)
                metadata.title = map.songName
                metadata.original_title = map.mapName
                metadata.year = int(str(score)[:-3]) if score else None
                metadata.roles.clear()
                metadata.directors.clear()
                metadata.producers.clear()
                for author in map.levelAuthors:
                    role = metadata.roles.new()
                    role.role = "Mapping"
                    role.name = author
                for author in map.songAuthors:
                    role = metadata.roles.new()
                    role.role = "Music"
                    role.name = author
                metadata.posters[map.poster] = Proxy.Media(HTTP.Request(map.poster))
                metadata.art[map.poster] = Proxy.Media(HTTP.Request(map.poster))


def getIdFromFilename(filename):
    match = re.search(r"^(.*?)\s*\(", filename)
    if match:
        return match.group(1)


def getScoreFromFilename(filename):
    match = re.search(r"_(\d+).mkv", filename)
    if match:
        return match.group(1)
    return "No Score"


def getMapHash(id):
    request = urllib2.Request(beatSaverBaseUrl.format(id), headers={"Accept": "application/json"})
    try:
        response = urllib2.urlopen(request)
        mapJson = json.loads(response.read())
        return mapJson['versions'][0]['hash']
    except urllib2.HTTPError as e:
        Log.Info("HTTP Error:", e.code)
    except urllib2.URLError as e:
        Log.Info("URL Error:", e.reason)
    except Exception as e:
        Log.Info("General Error:", e)


class Map:
    def __init__(self, id, difficulty):
        if id[0] == '#':
            self.initFromLocal(id)
        else:
            self.initFromBeatSaver(id, difficulty)

    def initFromLocal(self, id):
        path = os.path.join('..', 'SongMetadata', 'SongMetadata.ini')
        config = ConfigParser.ConfigParser()
        config.read(path)

        self.id = id
        self.url = config.get(id, 'url')
        self.mapName = config.get(id, 'mapName')
        self.mapDesciption = config.get(id, 'mapDesciption')
        self.songName = config.get(id, 'songName')
        self.songAuthors = config.get(id, 'songAuthors')
        self.levelAuthors = config.get(id, 'levelAuthors')
        self.bpm = config.get(id, 'bpm')
        self.duration = config.get(id, 'duration')
        self.poster = config.get(id, 'poster')

    def initFromBeatSaver(self, id, difficulty):
        self.id = id
        self.url = beatSaverBaseUrl.format(self.id)
        request = urllib2.Request(self.url, headers={"Accept": "application/json"})
        try:
            response = urllib2.urlopen(request)
            mapJson = json.loads(response.read())
            self.mapName = mapJson['name']
            self.mapDesciption = mapJson['description']
            self.songName = mapJson['metadata']['songName']
            self.songAuthors = self.seperateAuthors(mapJson['metadata']['songAuthorName'])
            self.levelAuthors = self.seperateAuthors(mapJson['metadata']['levelAuthorName'])
            self.bpm = mapJson['metadata']['bpm']
            self.duration = mapJson['metadata']['duration']
            self.upvotes = mapJson['stats']['upvotes']
            self.downvotes = mapJson['stats']['downvotes']
            self.rating = float(float(self.upvotes) / (float(self.upvotes) + float(self.downvotes)))
            self.poster = mapJson['versions'][0]['coverURL']
            self.hash = mapJson['versions'][0]['hash']
            if difficulty < 0:
                return
            self.difficulty = mapJson['versions'][0]['diffs'][self.mapDifficultyToJsonIndex(difficulty)]['difficulty']
            self.notes = mapJson['versions'][0]['diffs'][self.mapDifficultyToJsonIndex(difficulty)]['difficulty']
            self.bombs = mapJson['versions'][0]['diffs'][self.mapDifficultyToJsonIndex(difficulty)]['bombs']
            self.obstacles = mapJson['versions'][0]['diffs'][self.mapDifficultyToJsonIndex(difficulty)]['obstacles']
            self.nps = mapJson['versions'][0]['diffs'][self.mapDifficultyToJsonIndex(difficulty)]['nps']
        except urllib2.HTTPError as e:
            Log.Info("HTTP Error:", e.code)
        except urllib2.URLError as e:
            Log.Info("URL Error:", e.reason)
        except Exception as e:
            Log.Info("General Error:", e)

    def seperateAuthors(self, authors):
        unified_string = authors.replace(" & ", ", ")
        return unified_string.split(", ")

    def mapDifficultyToJsonIndex(self, difficulty):
        return (int(difficulty / 2)) - 1


class ScoreSaberScore:
    def __init__(self, mapHash, mapScore):
        score = self.findScore(mapHash, mapScore)
        if score is None:
            raise Exception("Score konnte nicht gefunden werden!")
        self.rank = score['score']['rank']
        self.baseScore = score['score']['baseScore']
        self.pp = score['score']['pp']
        self.badCuts = score['score']['badCuts']
        self.missedNotes = score['score']['missedNotes']
        self.maxCombo = score['score']['maxCombo']
        self.fullCombo = score['score']['fullCombo']
        self.timeSet = score['score']['timeSet']
        self.accuracy = float(self.baseScore) / float(score['leaderboard']['maxScore']) * 100
        self.rating = self.getRating(self.accuracy)
        self.difficulty = score['leaderboard']['difficulty']['difficulty']
        self.threeSixty = score['leaderboard']['difficulty']['gameMode'] == "SoloGenerated360Degree"

    def findScore(self, mapHash, mapScore):
        page = 0
        while True:
            request = urllib2.Request(scoreSaberPlayerScoresUrl.format(scoresaberid, page),
                                      headers={"Accept": "application/json", "User-Agent": "BeatSaberPlexAgent/1.0"})
            try:
                response = urllib2.urlopen(request)
                scoreJson = json.loads(response.read())
                if len(scoreJson['playerScores']) == 0:
                    break
                for score in scoreJson['playerScores']:
                    hash = str(score['leaderboard']['songHash']).upper()
                    refScore = int(str(score['score']['baseScore'])[:-3])
                    if hash.upper() == str(mapHash).upper() and refScore == mapScore:
                        return score
            except urllib2.HTTPError as e:
                Log.Info("HTTP Error:", e.code)
                break
            except urllib2.URLError as e:
                Log.Info("URL Error:", e.reason)
                break
            except Exception as e:
                Log.Info("General Error:", e)
                break
            page += 1

    def __str__(self):
        return ("Rank: {}\n"
                "Base Score: {}\n"
                "Max Combo: {}\n"
                "Full Combo: {}\n"
                "Zeit gesetzt: {}\n"
                "Genauigkeit: {:.2f}%\n"
                "Bewertung: {}").format(self.rank, self.baseScore, self.maxCombo,
                                        'Ja' if self.fullCombo else 'Nein',
                                        self.timeSet, self.accuracy, self.rating)

    def getRating(self, accuracy):
        if accuracy > 90:
            return "SS"
        elif accuracy > 80:
            return "S"
        elif accuracy > 65:
            return "A"
        elif accuracy > 50:
            return "B"
        elif accuracy > 35:
            return "C"
        elif accuracy > 20:
            return "D"
        else:
            return "E"
