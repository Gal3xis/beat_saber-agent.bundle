import json
import urllib2
import re
import os
import configparser

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
               results.Append(MetadataSearchResult(id = "{}_{}".format(map.mapName,score), score = score, name=map.mapName, lang=Locale.Language.NoLanguage))

    def update_poster(self, metadata, link, base_path = None):
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
                map = Map(id)
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
                if map.hash != null:
                    try:
                        Log("Find score for map {}".format(map.mapName))
                        mapScore = ScoreSaberScore(map.hash,score)
                        metadata.summary = "{}\n{}".format("https://beatsaver.com/maps/{}".format(map.id),mapScore)
                        metadata.content_rating = str(mapScore.rating)
                        metadata.rating = float(mapScore.accuracy)*10
                        metadata.rating_image = 'https://uxwing.com/wp-content/themes/uxwing/download/seo-marketing/accurate-icon.png'
                    except Exception as e:
                        raise Exception("Score wurde nicht gefunden:\n Map: {}\nMapHash: {}\nScore: {}\n".format(map.mapName,map.hash,score))
                
    
def getIdFromFilename(filename):
    match = re.search(r"^(.*?)\s*\(", filename)
    if match:
        return match.group(1)
    
def getScoreFromFilename(filename):
    match = re.search(r"_(\d+).mkv", filename)
    if match:
        return match.group(1)
    return "No Score"
    
class Map:
    def __init__(self,id):
        if id[0] == '#':
            self.initFromLocal(id)
        else:
            self.initFromBeatSaver(id)

    def initFromLocal(self, id):
        path = 'SongMetadata.ini'
        config = configparser.ConfigParser()
        config.read(path)

        self.id = id
        self.url = config[id]['url']
        self.mapName = config[id]['mapName']
        self.mapDesciption = config[id]['mapDesciption']
        self.songName = config[id]['songName']
        self.songAuthors = config[id]['songAuthors']
        self.levelAuthors = config[id]['levelAuthors']
        self.bpm = config[id]['bpm']
        self.duration = config[id]['duration']
        self.poster = config[id]['poster']

    def initFromBeatSaver(self,id):
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
        except urllib2.HTTPError as e:
            print("HTTP Error:", e.code)
        except urllib2.URLError as e:
            print("URL Error:", e.reason)
        except Exception as e:
            print("General Error:", e)


    def seperateAuthors(self,authors):
        unified_string = authors.replace(" & ", ", ")
        return unified_string.split(", ")     

class ScoreSaberScore:
    def __init__(self, mapHash, mapScore):
        score = self.findScore(mapHash, mapScore)
        if score is None:
            raise Exception("Score konnte nicht gefunden werden!")
        self.rank = score['score']['rank']
        self.baseScore = score['score']['baseScore']
        self.maxCombo = score['score']['maxCombo']
        self.fullCombo = score['score']['fullCombo']
        self.timeSet = score['score']['timeSet']
        self.accuracy = float(self.baseScore) / float(score['leaderboard']['maxScore'])
        self.rating = self.getRating(self.accuracy)

    def findScore(self, mapHash, mapScore):
        page = 0
        while True:
            request = urllib2.Request(scoreSaberPlayerScoresUrl.format(Prefs['scoresaberid'], page),
                                      headers={"Accept": "application/json", "User-Agent": "BeatSaberPlexAgent/1.0"})
            try:
                response = urllib2.urlopen(request)
                scoreJson = json.loads(response.read())
                if len(scoreJson['playerScores']) == 0:
                    break
                for score in scoreJson['playerScores']:
                    if str(score['leaderboard']['songHash']).upper() == str(mapHash).upper() and int(score['score']['baseScore']) == int(mapScore):
                        return score
            except urllib2.HTTPError as e:
                print("HTTP Error:", e.code)
                break
            except urllib2.URLError as e:
                print("URL Error:", e.reason)
                break
            except Exception as e:
                print("General Error:", e)
                break
            page += 1

    def __str__(self):
        return ("Rang: {}\n"
                "Score: {}\n"
                "Max Combo: {}\n"
                "Full Combo: {}\n"
                "Genauigkeit: {:.2f}%\n"
                "Bewertung: {}\n"
                "Datum: {}\n".format(self.rank, self.baseScore, self.maxCombo,
                                        'Ja' if self.fullCombo else 'Nein',
                                        self.accuracy*100, self.rating,self.timeSet))
    def getRating(self,accuracy):
        if accuracy > 0.90:
            return "SS"
        elif accuracy > 0.80:
            return "S"
        elif accuracy > 0.65:
            return "A"
        elif accuracy > 0.50:
            return "B"
        elif accuracy > 0.35:
            return "C"
        elif accuracy > 0.20:
            return "D"
        else: return "E"