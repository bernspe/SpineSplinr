import datetime
import logging

from rest_framework import serializers
from rest_framework.fields import ChoiceField


from splineapp.models import SpineSplineModel, SpineSplineCollection, SpineSplineDiagnosis

logger = logging.getLogger(__name__)




class SpineSplineSerializer(serializers.ModelSerializer):
    owner = serializers.ReadOnlyField(source='owner.username')
    owner_fullname = serializers.ReadOnlyField(source='owner.get_full_name')
    owner_birthday = serializers.ReadOnlyField(source='owner.date_of_birth')
    id = serializers.ReadOnlyField()
    #img = SerializerMethodField('prot_img')
    #resized_img=SerializerMethodField('prot_resized_img')
    #modified_img=SerializerMethodField('prot_modified_img')

    def create(self, validated_data):
        try:
            title = validated_data['title']
            if '&owner' in title:
                owner = validated_data['owner']
                owner_name = owner.get_full_name()
                title=title.replace('&owner', owner_name)
            if '&created' in title:
                created = datetime.datetime.now()
                created_string = created.strftime("%d.%m.%Y, %H:%M:%S")
                title=title.replace('&created', created_string)
            validated_data['title'] = title
        except:
            pass

        return SpineSplineModel.objects.create(**validated_data)

    def validate(self,data):
        try:
            value=data['created']
            if type (value) == datetime.date:
                data['created']= datetime.datetime.combine(date=value,time=datetime.datetime.now().time())
        except:
            pass
        return data


    def prot_img(self, ssm):
        if ssm.status == 'PROTECTED':
            return ssm.protected_resized_img.url
        else:
            return ssm.img.url

    def prot_resized_img(self,ssm):
        if ssm.status=='PROTECTED':
            return ssm.protected_resized_img.url
        else:
            return ssm.resized_img.url

    def prot_man_labeled_img(self,ssm):
        if ssm.status=='PROTECTED':
            return ssm.protected_man_labeled_img.url
        else:
            return ssm.man_labeled_img.url

    def prot_modified_img(self,ssm):
        if ssm.status=='PROTECTED':
            return ssm.protected_modified_img.url
        else:
            return ssm.modified_img.url

    class Meta:
        model = SpineSplineModel
        validators = []
        fields = '__all__'

class SpineSplineCollectionSerializer(serializers.ModelSerializer):
    owner = serializers.ReadOnlyField(source='owner.username')
    owner_fullname = serializers.ReadOnlyField(source='owner.get_full_name')
    owner_birthday = serializers.ReadOnlyField(source='owner.date_of_birth')
    diagnoses = serializers.SerializerMethodField('getdiagnoses')

    def validate_items(self,value):
        """
        Check that ssm's date is within time range of this collection
        :param value:
        :return:
        """
        item_created = value.created
        time_duration = self.created - item_created
        if abs(time_duration.days) > 45:
            raise serializers.ValidationError('SSM Date outlier')
        return value

    def getdiagnoses(self,scol):
        serializer=SpineSplineDiagnosisSerializer(scol.diagnoses,many=True)
        return serializer.data

    class Meta:
        model = SpineSplineCollection
        fields = '__all__'

class SpineSplineDiagnosisSerializer(serializers.ModelSerializer):
    physician_fullname = serializers.ReadOnlyField(source='responsible_physician.get_full_name')

    class Meta:
        model = SpineSplineDiagnosis
        fields = '__all__'
