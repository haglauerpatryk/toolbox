# Projekt – Logger oparty o hooki i dekoratory

## Wprowadzenie

Witam w moim projekcie.

Główną funkcjonalnością projektu jest **logger**. Struktura została jednak zaprojektowana w taki sposób, aby była możliwie prosta w rozbudowie — modularna, składana z elementów, które można łączyć podobnie jak klocki. Celowo unikałem używania tego określenia wprost, ponieważ mimo że projekt ten umożliwia zbudowanie loggera, nie jest to jedyna możliwość wykorzystania tego narzędzia. Taka jednak filozofia przyświecała projektowi od samego początku.

Poniżej, oprócz ogólnego opisu, zawarłem również **zastosowania oraz konteksty użycia**, wynikające z moich realnych potrzeb. Nie pochylałem się tutaj nad dokładnym opisem uruchamiania i obsługi narzędzia krok po kroku, ponieważ **zostało to przekazane wcześniej w konwersacji wraz z załączonymi grafikami**, pokazującymi:
- proces uruchamiania projektu,
- przykładowy output,
- miejsca umożliwiające manipulację poszczególnymi elementami.

---

## Setup (Linux)

Do uruchomienia projektu powinien wystarczyć poniższy setup:

```bash
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
python3 main.py
```

## Podstawowe pliki użytkowe

Całość użytkowania narzędzia opiera się na trzech głównych plikach:

- **`my_toolbox.py`**  
  Plik odpowiedzialny za konfigurację narzędzia.

- **`config.yaml`**  
  Plik konfiguracyjny, w którym definiujemy, które elementy mają być aktywne, a które nie.

- **`main.py`**  
  Plik, w którym narzędzie jest wykorzystywane — zawiera również załączone testy.

---

## Rozszerzalność i własne funkcjonalności

Dodawanie własnych funkcjonalności jest — zgodnie z opisem przekazanym wcześniej — **proste i bezpośrednie**. Projekt został zaprojektowany w taki sposób, aby nowe elementy można było wprowadzać bez ingerowania w istniejącą logikę aplikacji.

---

## Opis struktury plików

- **`core.py`**  
  Główna pętla wykonująca iterację po wszystkich zarejestrowanych hakach.

- **`decorators.py`**  
  Definicje dekoratorów.

- **`hooks.py`**  
  Definicje haków.

- **`log_dispatcher.py`**  
  Odpowiedzialny za definiowanie miejsc zapisu informacji (np. gdzie trafiają logi).

- **`logic.py`**  
  Miejsce na dodawanie logiki.

---

## Uwagi dotyczące stanu projektu

Mam świadomość, że projekt oferuje duże pole do refaktoryzacji. Na obecnym etapie **świadomie się tego nie podejmuję**, ponieważ priorytetem jest dla mnie:
- zapewnienie wsparcia dla ASGI/WSGI,
- możliwość wysyłania logów asynchronicznie,
- implementacja kilku dodatkowych funkcjonalności, które są dla mnie kluczowe funkcjonalnie.
Jednak mimo to uznałem, że jest wystarczająco interesujący, by go pokazać.
---

## Przykładowe konteksty użycia

Poniższe scenariusze wynikają z moich faktycznych potrzeb i doświadczeń:

1. **Klasyczne użycie jako logger**  
   Możliwość tworzenia struktur, różnych konfiguracji w pliku `yaml` oraz logiki w jednym miejscu, a następnie prostego „doklejenia” odpowiedniego dekoratora do funkcji — bez konieczności głębszego zastanawiania się nad implementacją. Ani bez nadmiernej ingerencji w kod.

2. **Usprawnienie pracy deweloperskiej**  
   Narzędzie pozwala bez ingerowania w główną logikę aplikacji dodać w pliku `yaml` fragmenty działające wyłącznie wtedy, gdy na przykład: `DEBUG == True`.
   Nie wpływa to na środowisko produkcyjne, a deweloperowi umożliwia m.in.:
   - wypisywanie nazw wywoływanych funkcji,
   - śledzenie czasu wykonania,
   - sprawdzanie poprawności typów wartości, 
   - itp. 
   bez dodawania `print()` ani podobnych instrukcji wewnątrz funkcji.

3. **Ad hoc dekorator do wychwytywania błędów**  
   Potrzeba ta pojawiła się u mnie szczególnie przy pracy z LLM-ami.  
   Są to narzędzia bardzo użyteczne (symulowanie funkcjonalności, NLP, itp.), jednak jednocześnie niestabilne. Zdarza się, że kod przestaje działać z niewiadomego powodu, co wymusza dodawanie dodatkowego kodu diagnostycznego.  
   To narzędzie pozwala:
   - zbierać maksymalną ilość informacji podczas wywołania funkcji,
   - **wysyłać logi wyłącznie w przypadku wystąpienia błędu**.

---

## Kierunki dalszego rozwoju

Aktualnie pracuję nad następującymi kierunkami rozwoju projektu:

1. **Zastąpienie klasycznego `try/except` dekoratorem**  
   Na pierwszy rzut oka może to brzmieć niedorzecznie, jednak potrzeba ta pojawiła się u mnie poraz pierwszy w kontekście systemów płatności.  
   Poza obsługą szczęśliwych ścieżek, należy tam uwzględniać bardzo długą listę potencjalnych błędów, jakie mogą mieć miejsce. W efekcie:
   - proste funkcje (kilkanaście linii) rozrastają się do kilkudziesięciu,
   - kod staje się „zabetonowany” i trudny w dalszej rozbudowie.  

   Moim celem jest podejście, w którym wnętrze funkcji odpowiada wyłącznie na pytanie:  
   **„Co ta funkcja ma zrobić?”**
   Oraz trzymać się zasady, według której każda funkcja wykonuje jedną rzecz.

2. **Wsparcie dla ASGI/WSGI oraz programowania asynchronicznego**  
   Jest to bezpośrednia kontynuacja założeń architektonicznych projektu.