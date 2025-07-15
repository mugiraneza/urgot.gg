from django.urls import path, include
from rest_framework.routers import DefaultRouter
from . import views

router = DefaultRouter()    
# router.register(r'matches', views.MatchViewSet)
# router.register(r'participants', views.ParticipantViewSet)
# router.register(r'teams', views.TeamViewSet)
# router.register(r'bans', views.BanViewSet)
# router.register(r'objectives', views.ObjectiveViewSet)
# router.register(r'deaths', views.DeathViewSet)

urlpatterns = [
    path('', include(router.urls)),
    path('import/import-matches/', views.TriggerMatchImportViewSet.as_view(), name='import-matches'),  # note le `/` à la fin
    path('import/count-matches/', views.MatchcountViewSet.as_view(), name='count-matches'),  # idem ici
    path('import/import-status/', views.ImportStatusView.as_view(), name='import-status'),  # idem ici
    path('stats/poste-last-60-day/', views.PositionStatsView.as_view(), name='poste-last-60-day'), 
    path("stats/yearly-win-positions/", views.YearlyWinLossByPositionView.as_view(),name='yearly-win-positions'),
    path("stats/match-details/", views.DetailedMatchStatsView.as_view(),name='match-details'),
    path("stats/champion-pool-by-role/", views.RoleChampionStatsView.as_view(),name='champion-pool-by-role'),
    path("stats/global-stats-stat/", views.GlobalStatsView.as_view(),name='global-stats-stat'),
    path("stats/global-modes-played-stat/", views.GameModesPlayedStatsView.as_view(),name='global-modes-played-stat'),
    path("stats/death-timeline-by-games-id-stat/", views.DeathTimelineView.as_view(),name='death-timeline-by-games-id-stat'),
    path("stats/game-duration-outcomes-distribution/", views.GameDurationOutcomeDistributionView.as_view(), name='game-duration-outcomes-distribution'),
    path("search/findusmmoner-name/", views.FindNewUsernameView.as_view(), name='findusmmoner-name'),
    path("map/death-map-image/", views.DeathMapImageView.as_view(), name="death-map-image"),
    path("map/death-map-image-single-summoner/", views.DeathMapImageByUserView.as_view(), name="death-map-image-single-summoner"),


]
