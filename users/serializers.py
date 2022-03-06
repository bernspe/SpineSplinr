from datetime import date

from django.contrib.auth.models import Group
from rest_framework import serializers

from SpineSplinr.settings import HELPDESK_NAME, GEN_STAFF_USER
from users.models import User, ConsentContent, consent, Userrole, UserProof, get_default_expiry, Device
from django.db.models import Q, F


def calculate_age(born):
    today = date.today()
    return today.year - born.year - ((today.month, today.day) < (born.month, born.day))


class UserroleSerializer(serializers.ModelSerializer):
    class Meta:
        model = Userrole
        fields = '__all__'

    def to_representation(self, instance):
        data = super().to_representation(instance)
        if (data['proof']=='nan'):
            data['proof'] = []
        return data

class GroupSerializer(serializers.ModelSerializer):
    class Meta:
        model = Group
        fields = ('name',)

class UserSerializer(serializers.ModelSerializer):
    missing = serializers.SerializerMethodField()
    rolescategories = serializers.SerializerMethodField()
    groups = GroupSerializer(many=True)
    class Meta:
        model = User
        fields = '__all__'
        read_only_fields = ['is_active','is_staff','is_superuser','is_admin','proofs','proofstatus','missing', 'groups']

    def get_missing(self,user):
        _, missinglabels = user.set_user_group()
        return missinglabels

    def get_rolescategories(self,user):
        cats=[]
        for r in user.roles.all():
            cats.append(r.category)
        return set(cats)

    def update(self, instance, validated_data):
        try:
            if (validated_data['date_of_birth']):
                if calculate_age(validated_data['date_of_birth'])>17:
                    #exclude med and staff
                    ms=instance.roles.filter(Q(category='Med')|Q(category='Staff'))
                    if (len(ms)==0):
                        instance.roles.add('Adult')
                        instance.roles.remove('Child')
                        instance.roles.remove('Child16')
                else:
                    if calculate_age(validated_data['date_of_birth']) > 15:
                        instance.roles.add('Child16')
                    else:
                        instance.roles.add('Child')
                    instance.roles.remove('Adult')
                instance.save()
        except:
            pass
        instance = super(UserSerializer, self).update(instance, validated_data)
        return instance

class StaffUserSerializer(serializers.ModelSerializer):
    missing = serializers.SerializerMethodField()
    rolescategories = serializers.SerializerMethodField()
    groups = GroupSerializer(many=True)
    helpdesk_caseroom_waiting = serializers.SerializerMethodField()

    class Meta:
        model = User
        fields = '__all__'

    def get_missing(self,user):
        _, missinglabels = user.set_user_group()
        return missinglabels

    def get_rolescategories(self,user):
        cats=[]
        for r in user.roles.all():
            cats.append(r.category)
        return set(cats)

    def get_helpdesk_caseroom_waiting(self,user):
        # this returns all the helpdeskcaserooms with news for the staff
        from caserooms.models import CaseRoom
        cr=CaseRoom.objects.filter(Q(title__contains=HELPDESK_NAME) &Q(owner_id__exact=user.username) & Q(news_for_participants__username__exact=GEN_STAFF_USER['username']))
        return [str(c.id) for c in cr]

    def update(self, instance, validated_data):
        try:
            if (validated_data['date_of_birth']):
                if calculate_age(validated_data['date_of_birth']) > 17:
                    # exclude med and staff
                    ms = instance.roles.filter(Q(category='Med') | Q(category='Staff'))
                    if (len(ms) == 0):
                        instance.roles.add('Adult')
                        instance.roles.remove('Child')
                        instance.roles.remove('Child16')
                else:
                    if calculate_age(validated_data['date_of_birth']) > 15:
                        instance.roles.add('Child16')
                    else:
                        instance.roles.add('Child')
                    instance.roles.remove('Adult')
                instance.save()
        except:
            pass
        instance = super(StaffUserSerializer, self).update(instance, validated_data)
        return instance


class UserNameEmailSerializer(serializers.ModelSerializer):
    name = serializers.SerializerMethodField('getname')

    class Meta:
        model = User
        fields = ('username','name','first_name','last_name','date_of_birth','email','document','roles','caregiver','postal_address')
    def getname(self, user):
        return user.first_name+' '+user.last_name

class MedicalStaffSerializer(serializers.ModelSerializer):
    name = serializers.SerializerMethodField('getname')
    class Meta:
        model = User
        fields = ('name','username')

    def getname(self, user):
        return user.first_name+' '+user.last_name

class ForgotPasswordSerializer(serializers.ModelSerializer):
    def update(self, instance, validated_data):
        instance.set_password(validated_data['password'])
        instance.is_emailvalidated=True
        instance.emailtoken=''
        instance.expires=get_default_expiry()
        for child in instance.dependent_children.all():
            child.expires=get_default_expiry()
            child.save()
        instance.save()
        return instance

    def validate(self, data):
        token = data.get('emailtoken')
        user = User.objects.filter(username=data.get('username'), emailtoken=token)
        if (len(user)==0):
            raise serializers.ValidationError({"emailtoken": "Emailtoken do not match or user does not exist"})
        return data

    class Meta:
        model = User
        fields = ('username','password','emailtoken','is_emailvalidated')

class RegisterSerializer(serializers.ModelSerializer):
    def update(self, instance, validated_data):
        validated_data.pop('password',None)
        instance.save()
        return instance

    def validate(self, data):
        try:
            email=data.get('email')
            if email:
                data.update({'email':email.lower()})
            user = User.objects.filter(username=data.get('username'))
            email=User.objects.filter(email=email)
            if ((len(user) > 0) | (len(email)>0)):
                raise serializers.ValidationError(("Username or email already exists"))
        except User.DoesNotExist:
            pass
        return data

    def create(self, validated_data, instance=None):
        roles_data=[]
        try:
            roles_data = validated_data.pop('roles')
        except:
            pass
        user = User.objects.create(**validated_data)
        user.set_password(validated_data['password'])
        for r in roles_data:
            user.roles.add(r)
        user.save()
        return user

    class Meta:
        model = User
        fields = '__all__'

class DeviceSerializer(serializers.ModelSerializer):
    class Meta:
        model = Device
        fields = '__all__'

    def create(self, validated_data):
        uuid = validated_data['uuid']
        user = validated_data['referring_User']
        dev = Device.objects.filter(Q(uuid=uuid)&Q(referring_User=user))
        if dev.exists():
            return dev.first()
        else:
            dev=Device.objects.create(**validated_data)
            return dev

class ProofSerializer(serializers.ModelSerializer):
    class Meta:
        model = UserProof
        fields = '__all__'

class ConsentContentSerializer(serializers.ModelSerializer):
    class Meta:
        model = ConsentContent
        fields = '__all__'


class ConsentSerializer(serializers.ModelSerializer):
    class Meta:
        model = consent
        fields = '__all__'

    def create(self, validated_data):
        members_data = validated_data.pop('involved_users', None)
        co = consent.objects.create(**validated_data)
        if members_data:
            for m in members_data:
                co.involved_users.add(m)
        co.save()
        return co

class ConsentWithContentSerializer(serializers.ModelSerializer):
    content = serializers.SerializerMethodField('getcontent')

    class Meta:
        model = consent
        fields = '__all__'

    def getcontent(self, consent):
        con=consent.consent_content
        ser = ConsentContentSerializer(con)
        return ser.data