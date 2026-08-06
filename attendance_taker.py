import dlib
import numpy as np
import cv2
import pandas as pd
import os
import logging
import sqlite3
from datetime import datetime

class FaceRecognizerService:
    def __init__(self, detect_every=3):
        # Configuration
        self.detect_every = detect_every
        self.frame_cnt = 0
        self.tolerance = 0.4
        
        # Cache for intermediate frames
        self.last_results = [] 
        
        # Load Dlib models
        try:
            self.detector = dlib.get_frontal_face_detector()
            self.predictor = dlib.shape_predictor('data/data_dlib/shape_predictor_68_face_landmarks.dat')
            self.face_reco_model = dlib.face_recognition_model_v1("data/data_dlib/dlib_face_recognition_resnet_model_v1.dat")
        except Exception as e:
            logging.error(f"Error loading dlib models: {e}")
            raise
            
        # Load known faces database
        self.face_name_known_list = []
        self.face_features_known_list = []
        self._load_face_database()
        
        # Ensure SQLite DB is ready
        self._init_database()

    def _init_database(self):
        conn = sqlite3.connect("attendance.db")
        cursor = conn.cursor()
        create_table_sql = """CREATE TABLE IF NOT EXISTS attendance 
                              (name TEXT, time TEXT, date DATE, method TEXT, 
                               UNIQUE(name, date))"""
        cursor.execute(create_table_sql)
        conn.commit()
        conn.close()

    def _load_face_database(self):
        path_csv = "data/features_all.csv"
        if os.path.exists(path_csv):
            try:
                csv_rd = pd.read_csv(path_csv, header=None)
                for i in range(csv_rd.shape[0]):
                    self.face_name_known_list.append(csv_rd.iloc[i][0])
                    features = []
                    for j in range(1, 129):
                        val = csv_rd.iloc[i][j]
                        if pd.isna(val) or val == '':
                            features.append(0.0)
                        else:
                            features.append(float(val))
                    self.face_features_known_list.append(features)
                logging.info(f"Loaded {len(self.face_name_known_list)} faces from Database.")
            except Exception as e:
                logging.error(f"Error reading CSV: {e}")
        else:
            logging.warning("features_all.csv not found! Please register faces first.")

    @staticmethod
    def return_euclidean_distance(feature_1, feature_2):
        feature_1 = np.array(feature_1)
        feature_2 = np.array(feature_2)
        return np.sqrt(np.sum(np.square(feature_1 - feature_2)))

    def record_attendance(self, name, method="face_id"):
        # We wrap this in try-except so it doesn't crash the GUI if constraint fails
        current_date = datetime.now().strftime('%Y-%m-%d')
        current_time = datetime.now().strftime('%H:%M:%S')
        
        try:
            conn = sqlite3.connect("attendance.db")
            cursor = conn.cursor()
            cursor.execute("INSERT INTO attendance (name, time, date, method) VALUES (?, ?, ?, ?)", 
                           (name, current_time, current_date, method))
            conn.commit()
            conn.close()
            return True, "Recorded successfully"
        except sqlite3.IntegrityError:
            return False, "Already recorded today"
        except Exception as e:
            return False, str(e)

    def process_frame(self, frame_rgb):
        """
        Takes an RGB frame, runs detection/recognition, and returns bounding boxes with names.
        To save FPS, it only runs heavy Dlib tasks every `self.detect_every` frames.
        Returns: list of dicts [{'name': 'dimas', 'box': (left, top, right, bottom)}]
        """
        self.frame_cnt += 1
        
        if self.frame_cnt % self.detect_every != 0:
            return self.last_results

        faces = self.detector(frame_rgb, 0)
        results = []

        if len(faces) == 0:
            self.last_results = []
            return []

        for face in faces:
            # Get facial landmarks & 128D descriptor
            shape = self.predictor(frame_rgb, face)
            face_descriptor = self.face_reco_model.compute_face_descriptor(frame_rgb, shape)
            
            # Compare with database
            e_distances = []
            for known_feature in self.face_features_known_list:
                if str(known_feature[0]) != '0.0':
                    dist = self.return_euclidean_distance(face_descriptor, known_feature)
                    e_distances.append(dist)
                else:
                    e_distances.append(999999999)

            if e_distances:
                min_dist = min(e_distances)
                similar_person_num = e_distances.index(min_dist)
                
                if min_dist < self.tolerance:
                    person_name = self.face_name_known_list[similar_person_num]
                else:
                    person_name = "unknown"
            else:
                person_name = "unknown"

            results.append({
                'name': person_name,
                'box': (face.left(), face.top(), face.right(), face.bottom())
            })

        self.last_results = results
        return results
