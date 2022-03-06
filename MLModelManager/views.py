import seaborn as sns
import matplotlib.pyplot as plt
from rest_framework import viewsets, status
from rest_framework.decorators import api_view, permission_classes, action
from rest_framework.permissions import IsAuthenticated, AllowAny
from oauth2_provider.contrib.rest_framework import OAuth2Authentication
from rest_framework.response import Response

from MLModelManager.models import MLModel
from MLModelManager.serializers import MLModelSerializer
from MLModelManager.tasks import pushToRemoteConsole, runModelProcess
from SpineSplinr.settings import MLMODEL_DIR, MLMODEL_URL
from users.permissions import IsStaff

@api_view(['GET'])
@permission_classes([IsAuthenticated])
def get_mlmodel_types(request):
    a=[x[0] for x in MLModel.TYPES]
    return Response(a)

class MLModelManagerViewSet(viewsets.ModelViewSet):
    queryset = MLModel.objects.all()
    serializer_class = MLModelSerializer
    permission_classes = [IsAuthenticated, IsStaff]
    authentication_classes = [OAuth2Authentication]
    remote_active=False

    def get_queryset(self):
        return self.queryset.all()

    def perform_create(self, serializer):
        serializer.save(owner=self.request.user, status='created', files=self.request.FILES)

    def perform_update(self, serializer):
        serializer.save(files=self.request.FILES)

    @action(methods=['post'], detail=True, permission_classes=[AllowAny])
    def test_model(self, request, pk=None):
        """
        tests the Model specified by pk
        """
        try:
            dataset=request.data.get('dataset')
            number_imgs=request.data.get('number_imgs')
            runModelProcess.delay(dataset, pk=pk, number_imgs=number_imgs)
            return Response(data={'test_model':'started'}, status=status.HTTP_200_OK)
        except Exception as e:
            return Response(data={"test_model": str(e)}, status=status.HTTP_400_BAD_REQUEST)

    @action(methods=['get'], detail=True, permission_classes=[IsAuthenticated])
    def get_model_performance(self,request, pk=None):
        """
        Get a result graph for models performance
        :param request:
        :param pk:
        :return:
        """
        try:
            m=MLModel.objects.get(id=pk)
            df=m.getPerformance()
            if len(df)>0:
                sns.violinplot(data=df, palette="deep")
                mdir = MLMODEL_DIR + '/' + pk + '/'
                plt.savefig(mdir+'performances.png',dpi=300)
                return Response(data={'model_performance': MLMODEL_URL+pk+'/performances.png'}, status=status.HTTP_200_OK)
            else:
                return Response(data={"model_performance": "not enough data"}, status=status.HTTP_400_BAD_REQUEST)
        except Exception as e:
            return Response(data={"model_performance": str(e)}, status=status.HTTP_400_BAD_REQUEST)
