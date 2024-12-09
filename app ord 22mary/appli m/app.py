from flask import Flask, render_template, request, jsonify
import plotly.figure_factory as ff
import plotly.graph_objects as go

app = Flask(__name__)
   
# Fonctions d'ordonnancement
def fifo(jobs,num_machines):
    return sorted(jobs, key=lambda x: x['arrival_time'])   

def lpt(jobs):
    return sorted(jobs, key=lambda x: sum(x['processing_time']), reverse=True)

def spt(jobs):
    return sorted(jobs, key=lambda x: sum(x['processing_time']))

def lifo(jobs):
    return sorted(jobs, key=lambda x: x['arrival_time'], reverse=True)

def edd(jobs):  
    return sorted(jobs, key=lambda x: x['due_date'])

def no_idle(schedule, num_machines):
    # On part du dernier job et on ajuste les horaires si nécessaire
    for machine_idx in range(num_machines):
        for job_idx in range(1, len(schedule)):  # On commence par le deuxième job
            prev_finish_time = schedule[job_idx - 1][machine_idx][1]  # Fin du job précédent
            current_start_time = schedule[job_idx][machine_idx][0]  # Début du job actuel

            # Si la différence entre la fin du job précédent et le début du job actuel est > 0
            # Cela signifie qu'il y a un idle (temps d'inactivité)
            if current_start_time > prev_finish_time:
                # Déplacer le job actuel pour qu'il commence immédiatement après le précédent
                schedule[job_idx][machine_idx] = (
                    prev_finish_time, prev_finish_time + (schedule[job_idx][machine_idx][1] - schedule[job_idx][machine_idx][0])
                )
                
                # Réajuster les jobs suivants sur cette machine
                for next_job_idx in range(job_idx + 1, len(schedule)):
                    schedule[next_job_idx][machine_idx] = (
                        schedule[next_job_idx - 1][machine_idx][1],  # Commence après le job précédent
                        schedule[next_job_idx - 1][machine_idx][1] + (schedule[next_job_idx][machine_idx][1] - schedule[next_job_idx][machine_idx][0])
                    )
    return schedule

def no_wait(schedule, num_machines):
    # Appliquer la contrainte no_wait : un job commence dès que le précédent finit sur chaque machine
    for job_idx in range(len(schedule)):
        for machine_idx in range(1, num_machines):
            prev_finish_time = schedule[job_idx][machine_idx - 1][1]  # Fin du job sur la machine précédente
            current_start_time = schedule[job_idx][machine_idx][0]  # Début du job sur la machine actuelle

            # Le job doit commencer dès que la machine précédente est terminée
            if current_start_time < prev_finish_time:
                schedule[job_idx][machine_idx] = (
                    prev_finish_time, prev_finish_time + (schedule[job_idx][machine_idx][1] - schedule[job_idx][machine_idx][0])
                )
    return schedule

# Génération d'un diagramme de Gantt en unités temporelles
import plotly.graph_objects as go

# Génération d'un diagramme de Gantt pour Flow Shop
# Modification de la génération du Gantt pour prendre en compte plusieurs machines
def generate_gantt(jobs, schedule, num_machines):
    fig = go.Figure()
    
    # Couleurs pour les tâches (palette élargie pour éviter les répétitions fréquentes)
    colors = [
        '#FF5733', '#33FF57', '#3357FF', '#FF33A1', '#A133FF', '#5de5d3',
        '#9028bc', '#db9ef5', '#1e769e', '#61b7df'
    ]
    
    # Parcourir les jobs et leurs plannings
    for job_idx, job_schedule in enumerate(schedule):
        job_name = jobs[job_idx]['name']  # Identifiant du job
        
        for machine_idx, (start_time, finish_time) in enumerate(job_schedule):
            machine_name = f"M{machine_idx + 1}"  # Nom de la machine
            
            # Ajouter la tâche au graphique
            fig.add_trace(go.Bar(
                x=[finish_time - start_time],  # Longueur de la tâche
                y=[machine_name],  # Machine correspondante
                base=start_time,  # Temps de début
                orientation='h',  # Barres horizontales
                marker=dict(color=colors[job_name % len(colors)]),  # Assurer des couleurs uniques par job
                name=f"J{job_name} - M{machine_idx + 1}"
            ))

    # Mise en forme du diagramme
    fig.update_layout(
        title="Diagramme de Gantt (Flow Shop avec plusieurs machines)",
        xaxis=dict(title="Temps", showgrid=True, zeroline=True),
        yaxis=dict(title="Machines", showgrid=True, zeroline=True, categoryorder="category descending"),
        barmode='stack',
        showlegend=True,
        height=600,
        legend_title="Tâches"
    )
    
    return fig



def apply_constraints(schedule, num_machines, no_wait=False, no_idle=False):
    if no_wait:
        schedule = no_wait(schedule, num_machines)
    if no_idle:
        schedule = no_idle(schedule, num_machines)
    return schedule




# Calcul des métriques
def calculate_metrics(jobs, num_machines):
    # Initialisation
    machine_availability = [0] * num_machines  # Temps de disponibilité pour chaque machine
    cmax = 0
    total_tft = 0
    total_tt = 0

    # Matrice pour stocker les dates de début et de fin de chaque job sur chaque machine
    schedule = []

    # Calcul des métriques pour chaque job
    for job in jobs:
        job_start_time = job['arrival_time']  # Le début du job est l'heure d'arrivée
        job_schedule = []  # Stocker les temps de début et de fin pour ce job

        for machine_idx in range(num_machines):
            # La machine est disponible à `machine_availability[machine_idx]`
            # Le job peut être traité après avoir quitté la machine précédente
            start_time = max(job_start_time, machine_availability[machine_idx])

            # Fin de la tâche sur cette machine
            finish_time = start_time + job['processing_time'][machine_idx]

            # Ajouter les temps à la liste du job
            job_schedule.append((start_time, finish_time))

            # Mise à jour des disponibilités
            machine_availability[machine_idx] = finish_time
            job_start_time = finish_time  # Le job est prêt pour la prochaine machine

        # Ajouter le planning du job à la matrice globale
        schedule.append(job_schedule)

        # Mettre à jour les métriques globales
        cmax = max(cmax, finish_time)  # Cmax : temps de fin maximum
        total_tft += finish_time - job['arrival_time']  # Temps total de finition
        tardiness = max(finish_time - job['due_date'], 0)  # Retard (si dépassement de la date limite)
        total_tt += tardiness


    return cmax, total_tt, total_tft, schedule





@app.route('/')
def index():
    return render_template('index.html')

@app.route('/schedule', methods=['POST'])
def schedule():
    data = request.get_json()

    num_jobs = int(data['num_jobs'])
    num_machines = int(data['num_machines'])
    jobs = []

    # Construction de la liste des jobs à partir des données de la requête
    for i in range(num_jobs):
        job = {
            'name': i + 1,  # Index du job
            'arrival_time': float(data['arrival_times'][i]),
            'processing_time': list(map(float, data['processing_times'][i])),  # Liste des durées pour chaque machine
            'due_date': float(data['due_dates'][i])  # Date limite
        }
        jobs.append(job)

    # Méthode d'ordonnancement choisie
    method = data['method']
    if method == "FIFO":
        ordered_jobs = fifo(jobs)
    elif method == "LPT":
        ordered_jobs = lpt(jobs)
    elif method == "SPT":
        ordered_jobs = spt(jobs)
    elif method == "LIFO":
        ordered_jobs = lifo(jobs)
    elif method == "EDD":
        ordered_jobs = edd(jobs)
    else:
        return jsonify({'error': 'Méthode inconnue.'}), 400

    # Séquence des tâches (ordre des jobs après application de la méthode)
    sequence = [job['name'] for job in ordered_jobs]

    # Calcul des métriques et récupération du planning
    cmax, tt, tft, schedule = calculate_metrics(ordered_jobs, num_machines)

    # Vérification des contraintes et ajustement du planning
    no_wait = data.get('no_wait', False)  # Vérification si la contrainte no_wait est activée
    no_idle = data.get('no_idle', False)  # Vérification si la contrainte no_idle est activée

    # Appliquer les contraintes si elles sont activées
    if no_wait:
        schedule = no_wait(schedule, num_machines)
    if no_idle:
        schedule = no_idle(schedule, num_machines)

    # Diagramme de Gantt basé sur le planning ajusté
    gantt_graph = generate_gantt(ordered_jobs, schedule, num_machines)

    # Conversion du diagramme de Gantt en JSON pour l'envoyer au client
    graph_json = gantt_graph.to_json()

    # Résultat à retourner
    result = {
        'sequence': sequence,
        'cmax': cmax,
        'tft': tft,
        'tt': tt,
        'graph': graph_json
    }
    return jsonify(result)






if __name__ == '__main__':
    app.run(debug=True)