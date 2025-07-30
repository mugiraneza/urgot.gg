from django.urls import path, include
from rest_framework.routers import DefaultRouter
from . import views

router = DefaultRouter()    
router.register(r'basic/matches', views.MatchViewSet)
router.register(r'basic/participants', views.ParticipantViewSet)
router.register(r'basic/teams', views.TeamViewSet)
router.register(r'basic/bans', views.BanViewSet)
router.register(r'basic/objectives', views.ObjectiveViewSet)
router.register(r'basic/deaths', views.DeathViewSet)
router.register(r'basic/champions', views.ChampionViewSet)
router.register(r'basic/abilities', views.AbilityViewSet)
router.register(r'basic/items', views.ItemViewSet)
urlpatterns = [
    path('', include(router.urls)),
    path('import/import-champ-item/', views.TriggerChampImportViewSet.as_view(), name='import-champ-item'),  # note le `/` à la fin
    path('import/import-matches/', views.TriggerMatchImportViewSet.as_view(), name='import-matches'),  # note le `/` à la fin
    path('import/count-matches/', views.MatchcountViewSet.as_view(), name='count-matches'),  # idem ici
    path('import/import-status/', views.ImportStatusView.as_view(), name='import-status'),  # idem ici
    path('stats/poste-last-60-day/', views.PositionStatsView.as_view(), name='poste-last-60-day'), 
    path("stats/yearly-win-positions/", views.YearlyWinLossByPositionView.as_view(),name='yearly-win-positions'),
    path("stats/match-details/", views.DetailedMatchStatsView.as_view(),name='match-details'),
    path("stats/champion-pool-by-role/", views.RoleChampionStatsView.as_view(),name='champion-pool-by-role'),
    path("stats/global-stats/", views.GlobalStatsView.as_view(),name='global-stats'),
    path("stats/global-modes-played-stat/", views.GameModesPlayedStatsView.as_view(),name='global-modes-played-stat'),
    path("stats/death-timeline-by-games-id-stat/", views.DeathTimelineView.as_view(),name='death-timeline-by-games-id-stat'),
    path("stats/game-duration-outcomes-distribution/", views.GameDurationOutcomeDistributionView.as_view(), name='game-duration-outcomes-distribution'),
    path("stats/cs-per-minute-evolution/", views.CSPerMinuteEvolutionView.as_view(), name="cs-per-minute-evolution"),
    path("search/findusmmoner-name/", views.FindNewUsernameView.as_view(), name='findusmmoner-name'),
    path("map/death-map-image/", views.DeathMapImageView.as_view(), name="death-map-image"),
    path("map/death-map-image-single-summoner/", views.DeathMapImageByUserView.as_view(), name="death-map-image-single-summoner"),
    path("graph/cs-per-minute-evolution/", views.CSPerMinuteGraphView.as_view(), name="graph-cs-per-minute-evolution"),
    path("stats/avg-cs-per-min-last10/", views.AverageCsPerMinByChampionView.as_view(), name="avg-cs-per-min-last10"),
    path("graph/cs-per-minute-evolution-last10/", views.CSPerMinuteLast10GamesGraphView.as_view(), name="graph/cs-per-minute-evolution-last10/"),


]
