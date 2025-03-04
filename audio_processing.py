import os
import numpy as np
import librosa
import librosa.display
import matplotlib.pyplot as plt
from matplotlib.widgets import Button

def preprocess_audio(file_path, frame_length=2048, hop_length=512, show_example=None):
    """
    Applique le pre-emphasis, framing, and windowing au signal audio.

    Args:
        file_path (str) : Chemin d'accès au fichier audio.
        frame_length (int) : Longueur de chaque trame.
        hop_length (int) : Chevauchement entre les images.
        show_example (bool) : Indique s'il faut le signal audio et le signal accentué.

    Returns:
        tuple: Emphasized audio, framed and windowed signal, sample rate.
    """
    audio, sample_rate = librosa.load(file_path, sr=None)

    # Apply pre-emphasis
    pre_emphasis = 0.97
    emphasized_audio = np.append(audio[0], audio[1:] - pre_emphasis * audio[:-1])

    # Frame the signal
    frames = librosa.util.frame(emphasized_audio, frame_length=frame_length, hop_length=hop_length).T

    # Apply Hamming window
    windowed_frames = frames * np.hamming(frame_length)

    #  visualization
    if show_example:
        # Créer une figure 
        fig, axes = plt.subplots(1, 2, figsize=(10, 4))  # 1 ligne, 3 colonnes

        # Premier sous-graphe : Original Audio et Emphasized Audio
        axes[0].set_title("Original Audio")
        librosa.display.waveshow(audio, sr=sample_rate, ax=axes[0])
        axes[0].set_xlabel("Time")
        axes[0].set_ylabel("Amplitude")

        # Deuxième sous-graphe : Emphasized Audio
        axes[1].set_title("Emphasized Audio")
        librosa.display.waveshow(emphasized_audio, sr=sample_rate, ax=axes[1])
        axes[1].set_xlabel("Time")
        axes[1].set_ylabel("Amplitude")

        # Troisième sous-graphe : Emphasized Audio + Framing + Windowed
        # axes[2].set_title("Emphasized Audio + Framing + Windowed")
        # librosa.display.waveshow(windowed_frames.flatten(), sr=sample_rate, ax=axes[2])  # Flatten si nécessaire
        # axes[2].set_xlabel("Time")
        # axes[2].set_ylabel("Amplitude")

        # Ajuster l'espacement entre les sous-graphiques
        # plt.tight_layout()

        # Afficher la figure
        #  plt.show()


    return emphasized_audio, windowed_frames, sample_rate


def compute_lofar(audio, sr, freq_range=(0, 500), freq_interval=10, n_fft=2048, hop_length=512):
    """
    Compute the LOFAR spectrum with shape (51, number of frames).

    Args:
        audio (np.ndarray): Input audio signal.
        sr (int): Sampling rate of the audio signal.
        freq_range (tuple): Frequency range for LOFAR analysis (min_freq, max_freq).
        freq_interval (int): Frequency interval for analysis (e.g., 10 Hz).
        n_fft (int): Number of FFT points for STFT.
        hop_length (int): Hop length for STFT.

    Returns:
        np.ndarray: LOFAR spectrum of shape (51, number of frames).
    """
    # Compute the STFT
    stft_result = np.abs(librosa.stft(audio, n_fft=n_fft, hop_length=hop_length))
    
    # Convert to decibels
    stft_db = librosa.amplitude_to_db(stft_result, ref=np.max)

    # Get the frequency bins corresponding to the STFT
    freqs = librosa.fft_frequencies(sr=sr, n_fft=n_fft)

    # Filter frequencies 
    min_freq, max_freq = freq_range
    freq_indices = [i for i, f in enumerate(freqs) if min_freq <= f <= max_freq]

    # Downsample to match the desired frequency interval 
    target_freqs = np.arange(min_freq, max_freq + freq_interval, freq_interval)
    lofar_spectrum = []
    for target_freq in target_freqs:
        # Find the closest frequency bin to the target frequency
        closest_index = np.argmin(np.abs(freqs[freq_indices] - target_freq))
        lofar_spectrum.append(stft_db[freq_indices[closest_index], :]) 

    # Stack the results into a matrix of shape (51, number of frames)
    lofar_spectrum = np.vstack(lofar_spectrum)

    return lofar_spectrum

def extract_features(file_path, frame_length=2048, hop_length=512, n_features=12, save_path=None, show_example=None, show_shapes=None):
    """
    Extrait les caractéristiques audio, y compris MFCC, GFCC, CQT, LOFAR, et leurs caractéristiques delta.

    Args :
        file_path (str) : Chemin d'accès au fichier audio.
        frame_length (int) : Longueur de chaque image.
        hop_length (int) : Chevauchement entre les images.
        n_features (int) : Nombre de caractéristiques à extraire.
        save_path (str) : Chemin d'accès pour enregistrer les caractéristiques extraites.
        show_example (bool) : Indique s'il faut visualiser les caractéristiques.
    Returns:
        np.ndarray: Matrice de caractéristiques fusionnées.
        dic: Dictionnaire contenant les caractéristiques individuelles.
    """

    def compute_gfcc(audio, sr, n_filters=31, frame_length=None, hop_length=None, f_min=50):
        
        stft = np.abs(librosa.stft(audio, n_fft=int(sr * frame_length), hop_length=int(sr * hop_length)))
        gfcc = librosa.feature.mfcc(S=librosa.amplitude_to_db(stft), n_mfcc=n_filters)
        return gfcc

    if save_path and os.path.exists(save_path):
        return np.load(save_path)

    emphasized_audio, _, sample_rate = preprocess_audio(file_path, frame_length, hop_length, show_example) 

    # Extract features
    mfcc = librosa.feature.mfcc(y=emphasized_audio, sr=sample_rate, n_mfcc=n_features)
    gfcc = compute_gfcc(emphasized_audio, sample_rate, frame_length=frame_length/sample_rate, hop_length=hop_length/sample_rate)
    cqt = np.abs(librosa.cqt(y=emphasized_audio, sr=sample_rate, n_bins=41))
    #lofar = librosa.amplitude_to_db(np.abs(librosa.stft(emphasized_audio, n_fft=frame_length))[:50], ref=np.max)
    lofar =compute_lofar(emphasized_audio, sample_rate, freq_range=(0, 500), freq_interval=10)
    delta_mfcc = librosa.feature.delta(mfcc)
    delta_gfcc = librosa.feature.delta(gfcc)
    delta_cqt = librosa.feature.delta(cqt)
    delta_lofar = librosa.feature.delta(lofar)

    # Fuse features
    mgcl = np.concatenate([mfcc, gfcc, cqt, lofar], axis=0)
    delta_mgcl = librosa.feature.delta(mgcl)
    mgcl_delta_features = np.concatenate([mgcl, delta_mgcl], axis=0)
    if show_shapes:
        print(f" MFCC Shape: {mfcc.shape}")
        print(f" GFCC Shape: {gfcc.shape}")
        print(f" CQT Shape: {cqt.shape}")
        print(f" LOFAR Shape: {lofar.shape}")
        print(f" Delta-MFCC Shape: {delta_mfcc.shape}")
        print(f" Delta-GFCC Shape: {delta_gfcc.shape}")
        print(f" Delta-CQT Shape: {delta_cqt.shape}")
        print(f" Delta-LOFAR Shape: {delta_lofar.shape}")
        print(f" MGCL Shape: {mgcl.shape}")
        print(f" Delta-MGCL Shape: {delta_mgcl.shape}")
        print(f" MGCL-Delta Features Shape: {mgcl_delta_features.shape}")


    # Save features
    if save_path:
        np.save(save_path, mgcl_delta_features)
    features = {
            "MFCC": mfcc,
            "GFCC": gfcc,
            "CQT": cqt,
            "LOFAR": lofar,
            "Delta-MFCC": delta_mfcc,
            "Delta-GFCC": delta_gfcc,
            "Delta-CQT": delta_cqt,
            "Delta-LOFAR": delta_lofar,
            "MGCL": mgcl,
            "Delta-MGCL": delta_mgcl,
            "mgcl_delta_features": mgcl_delta_features
        }
    # Optional visualization
    if show_example:
        visualize_features(features, sample_rate=sample_rate)
  
    return  mgcl_delta_features, features

def close_all_figures(event):
    """Callback function to close all open figures."""
    plt.close('all')


def visualize_features(features, sample_rate=32000):
    """
    Visualise des paires de caractéristiques audio (par exemple, MFCC et Delta-MFCC) dans des sous-graphes séparés.

    Args :
        features (dict) : Dictionnaire contenant les noms des caractéristiques et les tableaux correspondants.
        sample_rate (int) : Taux d'échantillonnage de l'audio.
    """
    # Liste des couples de caractéristiques à afficher
    pairs = [
        ("MFCC", "Delta-MFCC"),
        ("GFCC", "Delta-GFCC"),
        ("CQT", "Delta-CQT"),
        ("LOFAR", "Delta-LOFAR"),
        ("MGCL", "Delta-MGCL")
    ]

    for feature1, feature2 in pairs:
        if feature1 in features and feature2 in features:
            fig, axes = plt.subplots(1, 2, figsize=(12, 4), sharex=True)

            # Afficher la première caractéristique (e.g., MFCC)
            if feature1 == "MFCC":
                img1 = librosa.display.specshow(features[feature1], sr=sample_rate, x_axis='time', cmap='viridis', ax=axes[0])
                axes[0].set_title(feature1)
                axes[0].set_ylabel("Channel Index")
                axes[0].set_yticks(np.arange(1, features[feature1].shape[0] + 1))
                axes[0].set_ylim(0.5, features[feature1].shape[0] - 0.5)
            elif feature1 == "GFCC":
                img1 = librosa.display.specshow(features[feature1], sr=sample_rate, x_axis='time', cmap='viridis', ax=axes[0])
                axes[0].set_title(feature1)
                axes[0].set_ylabel("Channel Index")
                axes[0].set_yticks(np.arange(0, 31, step=5))
            elif feature1 == "CQT":
                img1 = librosa.display.specshow(librosa.amplitude_to_db(np.abs(features[feature1]), ref=np.max),
                                                sr=sample_rate, x_axis='time', y_axis='hz', cmap='viridis', ax=axes[0])
                axes[0].set_title(feature1)
                axes[0].set_ylabel("Frequency (Hz)")
            elif feature1 == "LOFAR":
                img1 = librosa.display.specshow(librosa.amplitude_to_db(np.abs(features[feature1]), ref=np.max),
                                                sr=sample_rate, x_axis='time', y_axis='hz', cmap='viridis', ax=axes[0])
                axes[0].set_title(feature1)
                axes[0].set_ylabel("Frequency (Hz)")
            elif feature1 == "MGCL":
                img1 = librosa.display.specshow(features[feature1], sr=sample_rate, x_axis='time', cmap='viridis', ax=axes[0])
                axes[0].set_title(feature1)
                axes[0].set_yticks(np.arange(0, 135, step=20))
                axes[0].set_ylabel("Channel Index")

            fig.colorbar(img1, ax=axes[0], format='%+2.0f dB')

            # Afficher la deuxième caractéristique (e.g., Delta-xxx)
            img2 = librosa.display.specshow(features[feature2], sr=sample_rate, x_axis='time', cmap='viridis', ax=axes[1])
            axes[1].set_title(feature2)

            # Configurer les mêmes ticks pour les Delta
            if feature2 == "Delta-MFCC":
                axes[1].set_ylabel("Channel Index")
                axes[1].set_yticks(np.arange(1, features[feature2].shape[0] + 1))
                axes[1].set_ylim(0.5, features[feature2].shape[0] - 0.5)
            elif feature2 == "Delta-GFCC":
                axes[1].set_ylabel("Channel Index")
                axes[1].set_yticks(np.arange(0, 31, step=5))
            elif feature2 == "Delta-CQT":
                axes[1].set_ylabel("Frequency (Hz)")
                axes[1].set_yticks(np.arange(1, features[feature2].shape[0] + 1, step=5))
            elif feature2 == "Delta-LOFAR":
                axes[1].set_ylabel("Frequency (Hz)")
                axes[1].set_yticks(np.arange(1, features[feature2].shape[0] + 1, step=5))

            elif feature2 == "Delta-MGCL":
                axes[1].set_yticks(np.arange(0, 135, step=20))
                axes[1].set_ylabel("Channel Index")

            fig.colorbar(img2, ax=axes[1], format='%+2.0f dB')

            # Ajouter des labels communs
            for ax in axes:
                ax.set_xlabel("Time (s)")

            # Ajuster l'espacement entre les sous-graphiques
            plt.tight_layout()


    # figure pour mgcl_delta_features
    if "mgcl_delta_features" in features:
        plt.figure(figsize=(10, 6))
        img = librosa.display.specshow(features["mgcl_delta_features"], sr=sample_rate, x_axis='time', cmap='viridis')
        plt.colorbar(img, format='%+2.0f dB')
        plt.title("MGCL + Delta Features")
        plt.xlabel("Time (s)")
        plt.ylabel("Channel Index")
        plt.yticks(np.arange(0, 270, step=20))
        plt.tight_layout()

    # bouton pour fermer toutes les figures
    button_fig = plt.figure(figsize=(6, 2))
    ax_button = button_fig.add_axes([0.4, 0.4, 0.2, 0.4])  
    button = Button(ax_button, 'Close All')  
    button.on_clicked(close_all_figures)  

    # Afficher toutes les figures
    plt.show()